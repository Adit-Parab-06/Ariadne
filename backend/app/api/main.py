import json
import logging
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agents.events import REPLAY_DIR, get_bus
from app.agents.orchestrator import run_mission
from app.config import settings
from app.coordination.lab import run_concurrency_lab
from app.coordination.tasks import (
    create_run,
    decide_action,
    execute_action,
    get_run_tasks,
)
from app.db import graph_for, q
from app.memory.consolidate import consolidate
from app.memory.store import start_conversation
from app.tools import list_tools

logger = logging.getLogger(__name__)

VALID_TENANTS = {"northwind", "acme"}

app = FastAPI(
    title="Ariadne API",
    description="Graph-native multi-agent company brain API for incident response and institutional memory",
    version="1.0.0",
)

# CORS middleware configured from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Enforces API contract error format {error: str} for all HTTPExceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


def _check_tenant(tenant: str) -> None:
    if tenant not in VALID_TENANTS:
        raise HTTPException(status_code=404, detail=f"Unknown tenant '{tenant}'")


# ---------------------------------------------------------
# Request Models
# ---------------------------------------------------------

class MissionRequest(BaseModel):
    text: str
    mode: Literal["ask", "respond"] = "respond"
    conversation_id: Optional[str] = None


class ActionDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]


class ResolveRequest(BaseModel):
    note: str


class ConcurrencyLabRequest(BaseModel):
    tasks: int = Field(default=200, ge=1, le=1000)
    workers: int = Field(default=8, ge=1, le=64)


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Reports whether FalkorDB answers a query and the configured model name."""
    falkor_ok = False
    try:
        res = q("northwind", "RETURN 1 AS ping", readonly=True)
        falkor_ok = bool(res and len(res) > 0)
    except Exception as e:
        logger.warning(f"FalkorDB health check failed: {e}")

    return {
        "falkordb": falkor_ok,
        "model": settings.GEMINI_MODEL,
    }


@app.get("/api/tenants")
def get_tenants() -> List[Dict[str, str]]:
    """Returns available tenants."""
    return [
        {"id": "northwind", "name": "Northwind Cloud"},
        {"id": "acme", "name": "Acme Corp"},
    ]


@app.get("/api/tools")
def get_tools() -> List[Dict[str, Any]]:
    """Returns all registered agent and knowledge tools."""
    tools = list_tools()
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "agents": t["agents"],
            "readonly": t["readonly"],
        }
        for t in tools
    ]


@app.get("/api/{tenant}/graph/overview")
def get_graph_overview(tenant: str) -> Dict[str, Any]:
    """Returns knowledge-layer nodes and edges capped at 300 nodes, prioritizing services."""
    _check_tenant(tenant)
    g = graph_for(tenant)

    # Fetch nodes
    node_query = (
        "MATCH (n) "
        "WHERE n:Service OR n:Person OR n:Team OR n:Customer OR n:Incident OR n:Doc OR n:Decision "
        "RETURN n.id AS id, labels(n)[0] AS label, coalesce(n.name, n.title, n.id) AS name "
        "ORDER BY CASE WHEN n:Service THEN 0 ELSE 1 END, id "
        "LIMIT 300"
    )
    res_nodes = g.ro_query(node_query)
    nodes = []
    node_ids = set()
    for row in res_nodes.result_set:
        nid, label, name = row[0], row[1], row[2]
        nodes.append({"id": nid, "label": label, "name": name})
        node_ids.add(nid)

    if not node_ids:
        return {"nodes": [], "edges": []}

    # Fetch edges between returned nodes
    edge_query = (
        "MATCH (n)-[r]->(m) "
        "WHERE n.id IN $nids AND m.id IN $nids "
        "RETURN n.id AS src, type(r) AS rel, m.id AS dst "
        "LIMIT 600"
    )
    res_edges = g.ro_query(edge_query, {"nids": list(node_ids)})
    edges = [{"src": row[0], "rel": row[1], "dst": row[2]} for row in res_edges.result_set]

    return {"nodes": nodes, "edges": edges}


@app.post("/api/{tenant}/missions")
def post_mission(tenant: str, req: MissionRequest) -> Dict[str, str]:
    """Creates a run, starts orchestrator in a daemon thread, and returns run_id immediately."""
    _check_tenant(tenant)

    conv_id = req.conversation_id or start_conversation(tenant)
    run_id = create_run(tenant, mode=req.mode, mission=req.text, conversation_id=conv_id)
    bus = get_bus(tenant, run_id)

    # Spawn run_mission in background daemon thread
    t = threading.Thread(
        target=run_mission,
        kwargs={
            "tenant": tenant,
            "mode": req.mode,
            "text": req.text,
            "conversation_id": conv_id,
            "bus": bus,
            "run_id": run_id,
        },
        daemon=True,
    )
    t.start()

    return {"run_id": run_id, "conversation_id": conv_id}


@app.get("/api/{tenant}/runs/{run_id}/events")
def get_run_events(tenant: str, run_id: str):
    """Streams text/event-stream, replays from seq 0, sends heartbeats, closes after completion."""
    _check_tenant(tenant)
    g = graph_for(tenant)

    # Verify run exists
    res = g.ro_query("MATCH (r:Run {id: $rid}) RETURN r.id", {"rid": run_id})
    replay_path = REPLAY_DIR / f"{tenant}_{run_id}.jsonl"
    if (not res.result_set) and not replay_path.exists():
        raise HTTPException(status_code=404, detail=f"Unknown run '{run_id}'")

    def event_stream():
        bus = get_bus(tenant, run_id)
        for event in bus.subscribe(from_seq=0, timeout=15.0):
            if event.get("type") == "heartbeat" or event.get("seq") == -1:
                yield ": heartbeat\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/{tenant}/runs/{run_id}")
def get_run_detail(tenant: str, run_id: str) -> Dict[str, Any]:
    """Returns full run details including status, mission, answer, evidence, metrics, and actions."""
    _check_tenant(tenant)
    g = graph_for(tenant)

    cypher = (
        "MATCH (r:Run {id: $rid}) "
        "OPTIONAL MATCH (r)-[:ANSWERED]->(ans:Answer) "
        "RETURN r.status, r.mission, r.mode, r.started_at, r.ended_at, r.tool_calls, r.duration_ms, ans.text"
    )
    res = g.ro_query(cypher, {"rid": run_id})
    if not res.result_set:
        raise HTTPException(status_code=404, detail=f"Unknown run '{run_id}'")

    status, mission, mode, started_at, ended_at, tool_calls, duration_ms, answer_text = res.result_set[0]

    # Proposed actions
    act_cypher = (
        "MATCH (r:Run {id: $rid})-[:PROPOSED]->(a:Action) "
        "OPTIONAL MATCH (a)-[:EXECUTED_AS]->(se) "
        "RETURN a.id, a.kind, a.status, a.payload, a.ts, a.decided_at, se.id "
        "ORDER BY a.ts"
    )
    res_acts = g.ro_query(act_cypher, {"rid": run_id})
    actions = []
    for r in res_acts.result_set:
        actions.append({
            "id": r[0],
            "kind": r[1],
            "status": r[2],
            "payload": json.loads(r[3]) if r[3] else {},
            "ts": r[4],
            "decided_at": r[5],
            "side_effect_id": r[6],
        })

    # Evidence nodes and edges
    evidence = {"nodes": [], "edges": []}
    replay_path = REPLAY_DIR / f"{tenant}_{run_id}.jsonl"
    if replay_path.exists():
        try:
            nodes_by_id = {}
            edges_set = set()
            with open(replay_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    ev = json.loads(line)
                    if ev.get("type") == "tool.result":
                        ev_data = ev.get("data", {}).get("evidence", {})
                        for n in ev_data.get("nodes", []):
                            nodes_by_id[n["id"]] = n
                        for e in ev_data.get("edges", []):
                            edges_set.add((e["src"], e["rel"], e["dst"]))
            evidence = {
                "nodes": list(nodes_by_id.values()),
                "edges": [{"src": s, "rel": r, "dst": d} for s, r, d in edges_set],
            }
        except Exception as e:
            logger.warning(f"Failed to read evidence from replay: {e}")

    metrics = {
        "tool_calls": tool_calls or 0,
        "duration_ms": duration_ms or 0,
    }

    return {
        "id": run_id,
        "status": status,
        "mission": mission,
        "mode": mode,
        "answer": answer_text or "",
        "evidence": evidence,
        "metrics": metrics,
        "actions": actions,
    }


@app.get("/api/{tenant}/runs")
def list_runs(tenant: str) -> List[Dict[str, Any]]:
    """Returns recent runs with their status and metrics."""
    _check_tenant(tenant)
    g = graph_for(tenant)

    cypher = (
        "MATCH (r:Run) "
        "RETURN r.id, r.mission, r.mode, r.status, r.started_at, r.tool_calls, r.duration_ms "
        "ORDER BY r.started_at DESC "
        "LIMIT 20"
    )
    res = g.ro_query(cypher)
    runs = []
    for row in res.result_set:
        runs.append({
            "id": row[0],
            "mission": row[1],
            "mode": row[2],
            "status": row[3],
            "started_at": row[4],
            "metrics": {
                "tool_calls": row[5] or 0,
                "duration_ms": row[6] or 0,
            },
        })
    return runs


@app.post("/api/{tenant}/actions/{action_id}/decision")
def post_action_decision(tenant: str, action_id: str, req: ActionDecisionRequest) -> Dict[str, Any]:
    """Approves or rejects a proposed action; approval triggers simulated integration execution."""
    _check_tenant(tenant)

    try:
        if req.decision == "approve":
            decide_action(tenant, action_id, "approved")
            final_action = execute_action(tenant, action_id)
            return final_action
        else:
            final_action = decide_action(tenant, action_id, "rejected")
            return final_action
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/{tenant}/runs/{run_id}/resolve")
def resolve_run(tenant: str, run_id: str, req: ResolveRequest) -> Dict[str, Any]:
    """Consolidates completed run findings into long-term memory; marks run resolved."""
    _check_tenant(tenant)
    g = graph_for(tenant)

    cypher = (
        "MATCH (r:Run {id: $rid}) "
        "OPTIONAL MATCH (r)-[:ANSWERED]->(ans:Answer) "
        "RETURN r.status, r.mission, coalesce(ans.text, '')"
    )
    res = g.ro_query(cypher, {"rid": run_id})
    if not res.result_set:
        raise HTTPException(status_code=404, detail=f"Unknown run '{run_id}'")

    status, mission, ans_text = res.result_set[0]

    if status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Run '{run_id}' is in status '{status}'. Only 'completed' runs can be resolved.",
        )

    run_summary = f"Mission: {mission}. Answer: {ans_text}"
    try:
        memory_written = consolidate(tenant, run_id, req.note, run_summary)
        # Mark run resolved
        g.query("MATCH (r:Run {id: $rid}) SET r.status = 'resolved'", {"rid": run_id})
        return {"memory_written": memory_written}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Consolidation failed: {str(e)}")


@app.get("/api/{tenant}/memory")
def get_memory(tenant: str, kind: Optional[str] = Query(None, pattern="^(episode|fact|procedure)?$")) -> Any:
    """Returns episodic, semantic (fact), or procedural memory."""
    _check_tenant(tenant)
    g = graph_for(tenant)

    if kind == "episode":
        res = g.ro_query(
            "MATCH (e:Episode) "
            "RETURN e.id AS id, e.summary AS summary, e.goal AS goal, e.outcome AS outcome, e.ts AS ts "
            "ORDER BY e.ts DESC LIMIT 50"
        )
        return [{"id": r[0], "summary": r[1], "goal": r[2], "outcome": r[3], "ts": r[4]} for r in res.result_set]

    elif kind == "fact":
        res = g.ro_query(
            "MATCH (f:Fact) "
            "RETURN f.id AS id, f.subject_id AS subject_id, f.predicate AS predicate, f.text AS text, "
            "       f.valid_from AS valid_from, f.valid_to AS valid_to, f.confidence AS confidence "
            "ORDER BY f.valid_from DESC LIMIT 50"
        )
        return [
            {
                "id": r[0],
                "subject_id": r[1],
                "predicate": r[2],
                "text": r[3],
                "valid_from": r[4],
                "valid_to": r[5],
                "confidence": r[6],
            }
            for r in res.result_set
        ]

    elif kind == "procedure":
        res = g.ro_query(
            "MATCH (p:Procedure) "
            "RETURN p.id AS id, p.name AS name, p.trigger_text AS trigger_text, p.steps AS steps, "
            "       p.success_count AS success_count, p.fail_count AS fail_count, p.last_used AS last_used "
            "ORDER BY p.success_count DESC LIMIT 50"
        )
        return [
            {
                "id": r[0],
                "name": r[1],
                "trigger_text": r[2],
                "steps": json.loads(r[3]) if isinstance(r[3], str) and r[3].startswith("[") else r[3],
                "success_count": r[4],
                "fail_count": r[5],
                "last_used": r[6],
            }
            for r in res.result_set
        ]

    else:
        # Return all categories combined
        episodes = get_memory(tenant, "episode")
        facts = get_memory(tenant, "fact")
        procedures = get_memory(tenant, "procedure")
        return {"episodes": episodes, "facts": facts, "procedures": procedures}


@app.get("/api/{tenant}/tasks")
def get_tasks(tenant: str, run_id: str) -> Dict[str, Any]:
    """Returns task DAG and NEXT handoff edges for a run."""
    _check_tenant(tenant)
    task_data = get_run_tasks(tenant, run_id)
    return task_data


@app.post("/api/{tenant}/lab/concurrency")
def post_concurrency_lab(tenant: str, req: ConcurrencyLabRequest) -> Dict[str, Any]:
    """Runs high-concurrency atomic CAS task claim benchmark."""
    _check_tenant(tenant)
    results = run_concurrency_lab(tenant, tasks=req.tasks, workers=req.workers)
    return results
