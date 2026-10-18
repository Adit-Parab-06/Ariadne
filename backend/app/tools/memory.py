import json
from typing import Any, Dict, List, Optional

from app.db import graph_for
from app.embeddings import embed_texts
from app.memory.store import recall
from app.tools import tool
from app.tools.evidence import Evidence, ToolResult


@tool(
    name="recall_memory",
    description="Recalls relevant episodes, active facts, and procedures matching the query context and services.",
    params={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Alert or problem description"},
            "service_ids": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "List of service IDs under investigation",
            },
            "k": {"type": "integer", "default": 3, "description": "Number of memories to recall"},
        },
        "required": ["text"],
    },
    agents=["archivist"],
    readonly=True,
)
def recall_memory(
    tenant: str,
    text: str,
    service_ids: Optional[List[str]] = None,
    k: int = 3,
) -> ToolResult:
    sids = service_ids or []
    recalled = recall(tenant, text, sids, k)

    episodes = recalled["episodes"]
    facts = recalled["facts"]
    procedures = recalled["procedures"]
    evidence = recalled["evidence"]

    summary = (
        f"Recalled {len(episodes)} episode(s), {len(facts)} active fact(s), "
        f"and {len(procedures)} procedure(s)"
    )

    # Attach Cypher queries used conceptually
    cyphers = [
        "CALL db.idx.vector.queryNodes('Episode', 'embedding', $k, vecf32($vec)) YIELD node, score",
        "UNWIND $sids AS sid MATCH (f:Fact {subject_id: sid, valid_to: 0}) RETURN f",
        "MATCH (p:Procedure)-[:APPLIES_TO]->(s:Service) WHERE s.id IN $sids RETURN p",
    ]

    return ToolResult(
        summary=summary,
        data={
            "episodes": episodes,
            "facts": facts,
            "procedures": procedures,
        },
        evidence=evidence,
        cypher=cyphers,
    )


@tool(
    name="similar_incidents",
    description="Vector search for past incidents semantically similar to the current issue, boosted by graph service overlap.",
    params={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Incident symptom or alert text"},
            "service_ids": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "description": "Optional list of suspected service IDs for topological reranking",
            },
            "k": {"type": "integer", "default": 3, "description": "Number of incidents to return"},
        },
        "required": ["text"],
    },
    agents=["archivist"],
    readonly=True,
)
def similar_incidents(
    tenant: str,
    text: str,
    service_ids: Optional[List[str]] = None,
    k: int = 3,
) -> ToolResult:
    g = graph_for(tenant)
    sids = service_ids or []
    evidence = Evidence()
    cyphers: List[str] = []

    vectors = embed_texts([text], task_type="RETRIEVAL_QUERY")
    query_vec = vectors[0]

    cand_k = max(k * 3, 6)
    search_cypher = (
        "CALL db.idx.vector.queryNodes('Incident', 'embedding', $k, vecf32($vec)) "
        "YIELD node, score "
        "RETURN node.id, node.title, node.severity, node.summary, node.started_at, node.resolved_at, score"
    )
    cyphers.append(search_cypher)
    res = g.query(search_cypher, {"k": cand_k, "vec": query_vec})
    rows = res.result_set or []

    candidates = []
    for row in rows:
        iid, title, severity, summary, started_at, resolved_at, score = row
        dist = float(score)
        similarity = 1.0 - min(max(dist, 0.0), 1.0)

        # Check graph overlap: Did this incident affect any of service_ids?
        overlap_bonus = 0.0
        if sids:
            aff_cypher = (
                "MATCH (i:Incident {id: $iid})-[:AFFECTED]->(s:Service) "
                "WHERE s.id IN $sids "
                "RETURN count(s)"
            )
            aff_res = g.ro_query(aff_cypher, {"iid": iid, "sids": sids})
            if aff_res.result_set and aff_res.result_set[0][0] > 0:
                overlap_bonus = 0.25

        final_score = similarity + overlap_bonus
        candidates.append({
            "id": iid,
            "title": title,
            "severity": severity,
            "summary": summary,
            "started_at": started_at,
            "resolved_at": resolved_at,
            "similarity": round(similarity, 4),
            "final_score": round(final_score, 4),
        })

    candidates.sort(key=lambda c: c["final_score"], reverse=True)
    top_incidents = candidates[:k]

    # Fetch context: affected services, who resolved it, and resolved_with docs
    enriched_incidents = []
    for inc in top_incidents:
        iid = inc["id"]
        evidence.add_node(iid, "Incident", inc["title"])

        details_cypher = (
            "MATCH (i:Incident {id: $iid}) "
            "OPTIONAL MATCH (i)-[:AFFECTED]->(s:Service) "
            "OPTIONAL MATCH (p:Person)-[:RESOLVED]->(i) "
            "OPTIONAL MATCH (i)-[:RESOLVED_WITH]->(d:Doc) "
            "RETURN collect(DISTINCT {id: s.id, name: s.name}) AS affected, "
            "       collect(DISTINCT {id: p.id, name: p.name}) AS resolvers, "
            "       collect(DISTINCT {id: d.id, title: d.title}) AS docs"
        )
        cyphers.append(details_cypher)
        det_res = g.ro_query(details_cypher, {"iid": iid})
        affected, resolvers, docs = [], [], []
        if det_res.result_set:
            affected, resolvers, docs = det_res.result_set[0]

        # Filter out empty dicts from OPTIONAL MATCH
        affected = [a for a in affected if a.get("id")]
        resolvers = [r for r in resolvers if r.get("id")]
        docs = [d for d in docs if d.get("id")]

        for a in affected:
            evidence.add_node(a["id"], "Service", a["name"])
            evidence.add_edge(iid, "AFFECTED", a["id"])
        for r in resolvers:
            evidence.add_node(r["id"], "Person", r["name"])
            evidence.add_edge(r["id"], "RESOLVED", iid)
        for d in docs:
            evidence.add_node(d["id"], "Doc", d["title"])
            evidence.add_edge(iid, "RESOLVED_WITH", d["id"])

        enriched_incidents.append({
            **inc,
            "affected_services": affected,
            "resolved_by": resolvers[0] if resolvers else None,
            "resolved_with_doc": docs[0] if docs else None,
        })

    summary = f"Found {len(enriched_incidents)} similar incident(s)"
    return ToolResult(
        summary=summary,
        data={"incidents": enriched_incidents},
        evidence=evidence,
        cypher=cyphers,
    )
