import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple


@dataclass
class Evidence:
    nodes: Dict[str, Dict[str, str]] = field(default_factory=dict)  # id -> {id, label, name}
    edges: Set[Tuple[str, str, str]] = field(default_factory=set)   # (src, rel, dst)

    def add_node(self, node_id: str, label: str, name: str) -> None:
        self.nodes[node_id] = {"id": node_id, "label": label, "name": name}

    def add_edge(self, src: str, rel: str, dst: str) -> None:
        self.edges.add((src, rel, dst))

    def merge(self, other: "Evidence") -> "Evidence":
        self.nodes.update(other.nodes)
        self.edges.update(other.edges)
        return self

    def to_json(self) -> Dict[str, Any]:
        return {
            "nodes": list(self.nodes.values()),
            "edges": [{"src": s, "rel": r, "dst": d} for s, r, d in sorted(self.edges)],
        }


@dataclass
class ToolResult:
    summary: str
    data: Dict[str, Any]
    evidence: Evidence
    cypher: List[str]
    ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "data": self.data,
            "evidence": self.evidence.to_json(),
            "cypher": self.cypher,
            "ms": self.ms,
        }


def llm_view(result: ToolResult) -> Dict[str, Any]:
    """
    Returns a JSON-safe dict containing summary and data trimmed to about 6 KB.
    Crucial: Evidence is NOT sent to the LLM to preserve prompt context budget.
    """
    view = {
        "summary": result.summary,
        "data": result.data,
    }
    dumped = json.dumps(view, default=str)
    if len(dumped) > 6000:
        # Trim data representation
        view["data"] = {"trimmed": f"{str(result.data)[:5500]}... [truncated]"}
    return view
