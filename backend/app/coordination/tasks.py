import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.db import graph_for


def now_ms() -> int:
    return int(time.time() * 1000)


def create_run(
    tenant: str,
    mode: str,
    mission: str,
    conversation_id: Optional[str] = None,
) -> str:
    """Creates a new Run node in status 'running'."""
    g = graph_for(tenant)
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    ts = now_ms()

    cypher = (
        "CREATE (r:Run { "
        "  id: $id, mode: $mode, mission: $mission, status: 'running', "
        "  started_at: $ts, ended_at: 0, tool_calls: 0, duration_ms: 0 "
        "}) "
        "RETURN r.id"
    )
    g.query(cypher, {"id": run_id, "mode": mode, "mission": mission, "ts": ts})

    if conversation_id:
        g.query(
            "MATCH (r:Run {id: $rid}), (c:Conversation {id: $cid}) "
            "MERGE (r)-[:IN_CONVERSATION]->(c)",
            {"rid": run_id, "cid": conversation_id},
        )

    return run_id


def end_run(
    tenant: str,
    run_id: str,
    status: str,
    tool_calls: int,
    duration_ms: int,
) -> None:
    """Marks a Run as completed or failed with metrics."""
    g = graph_for(tenant)
    ts = now_ms()
    cypher = (
        "MATCH (r:Run {id: $rid}) "
        "SET r.status = $status, r.tool_calls = $tc, "
        "    r.duration_ms = $dur, r.ended_at = $ts"
    )
    g.query(cypher, {"rid": run_id, "status": status, "tc": tool_calls, "dur": duration_ms, "ts": ts})


def ensure_agent(tenant: str, agent_id: str, name: str, role: str) -> None:
    """Idempotently ensures an Agent node exists."""
    g = graph_for(tenant)
    cypher = "MERGE (a:Agent {id: $id}) SET a.name = $name, a.role = $role"
    g.query(cypher, {"id": agent_id, "name": name, "role": role})


def create_task(
    tenant: str,
    run_id: str,
    kind: str,
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    """Creates an 'open' Task node and links (Run)-[:HAS_TASK]->(Task)."""
    g = graph_for(tenant)
    task_id = f"tsk_{uuid.uuid4().hex[:8]}"
    ts = now_ms()
    payload_json = json.dumps(payload or {})

    cypher = (
        "MATCH (r:Run {id: $rid}) "
        "CREATE (t:Task { "
        "  id: $tid, run_id: $rid, kind: $kind, status: 'open', owner: '', "
        "  payload: $payload, result: '', created_at: $ts, claimed_at: 0, done_at: 0 "
        "}) "
        "CREATE (r)-[:HAS_TASK]->(t) "
        "RETURN t.id"
    )
    g.query(cypher, {"rid": run_id, "tid": task_id, "kind": kind, "payload": payload_json, "ts": ts})
    return task_id


def claim_task(tenant: str, task_id: str, agent_id: str) -> bool:
    """
    Attempts to atomically claim a task using a single conditional SET.
    No read-then-write in Python.
    Returns True only if the task was open and successfully claimed.
    """
    g = graph_for(tenant)
    ts = now_ms()
    claim_cypher = (
        "MATCH (t:Task {id: $tid}) WHERE t.status = 'open' "
        "SET t.status = 'claimed', t.owner = $agent, t.claimed_at = $ts "
        "RETURN t.id"
    )
    res = g.query(claim_cypher, {"tid": task_id, "agent": agent_id, "ts": ts})
    success = bool(res.result_set)

    if success:
        ensure_agent(tenant, agent_id, agent_id.capitalize(), "Worker Agent")
        link_cypher = (
            "MATCH (a:Agent {id: $aid}), (t:Task {id: $tid}) "
            "MERGE (a)-[:CLAIMED]->(t)"
        )
        g.query(link_cypher, {"aid": agent_id, "tid": task_id})

    return success


def complete_task(
    tenant: str,
    task_id: str,
    result: Dict[str, Any],
    owner: Optional[str] = None,
) -> bool:
    """
    Marks a task 'done' with result payload only if currently 'claimed' by that owner.
    """
    g = graph_for(tenant)
    ts = now_ms()
    res_str = json.dumps(result)

    if owner:
        cypher = (
            "MATCH (t:Task {id: $tid}) WHERE t.status = 'claimed' AND t.owner = $owner "
            "SET t.status = 'done', t.result = $res, t.done_at = $ts "
            "RETURN t.id"
        )
        res = g.query(cypher, {"tid": task_id, "owner": owner, "res": res_str, "ts": ts})
    else:
        cypher = (
            "MATCH (t:Task {id: $tid}) WHERE t.status = 'claimed' "
            "SET t.status = 'done', t.result = $res, t.done_at = $ts "
            "RETURN t.id"
        )
        res = g.query(cypher, {"tid": task_id, "res": res_str, "ts": ts})

    return bool(res.result_set)


def fail_task(
    tenant: str,
    task_id: str,
    error: str,
    owner: Optional[str] = None,
) -> bool:
    """Marks a task 'failed' only if currently 'claimed' by that owner."""
    g = graph_for(tenant)
    ts = now_ms()
    res_str = json.dumps({"error": error})

    if owner:
        cypher = (
            "MATCH (t:Task {id: $tid}) WHERE t.status = 'claimed' AND t.owner = $owner "
            "SET t.status = 'failed', t.result = $res, t.done_at = $ts "
            "RETURN t.id"
        )
        res = g.query(cypher, {"tid": task_id, "owner": owner, "res": res_str, "ts": ts})
    else:
        cypher = (
            "MATCH (t:Task {id: $tid}) WHERE t.status = 'claimed' "
            "SET t.status = 'failed', t.result = $res, t.done_at = $ts "
            "RETURN t.id"
        )
        res = g.query(cypher, {"tid": task_id, "res": res_str, "ts": ts})

    return bool(res.result_set)


def link_next(
    tenant: str,
    from_task_id: str,
    to_task_id: str,
    note: str = "",
) -> None:
    """Creates a NEXT handoff edge between tasks."""
    g = graph_for(tenant)
    ts = now_ms()
    cypher = (
        "MATCH (src:Task {id: $fid}), (dst:Task {id: $tid}) "
        "MERGE (src)-[:NEXT {note: $note, ts: $ts}]->(dst)"
    )
    g.query(cypher, {"fid": from_task_id, "tid": to_task_id, "note": note, "ts": ts})


def get_run_tasks(tenant: str, run_id: str) -> Dict[str, Any]:
    """Returns tasks and NEXT handoff edges for the given run."""
    g = graph_for(tenant)

    task_cypher = (
        "MATCH (r:Run {id: $rid})-[:HAS_TASK]->(t:Task) "
        "RETURN t.id, t.kind, t.status, t.owner, t.payload, t.result, t.created_at, t.claimed_at, t.done_at "
        "ORDER BY t.created_at ASC"
    )
    t_res = g.ro_query(task_cypher, {"rid": run_id})
    tasks = []
    for row in t_res.result_set or []:
        tasks.append({
            "id": row[0],
            "kind": row[1],
            "status": row[2],
            "owner": row[3],
            "payload": json.loads(row[4]) if row[4] else {},
            "result": json.loads(row[5]) if row[5] else {},
            "created_at": row[6],
            "claimed_at": row[7],
            "done_at": row[8],
        })

    next_cypher = (
        "MATCH (r:Run {id: $rid})-[:HAS_TASK]->(t1:Task)-[rel:NEXT]->(t2:Task) "
        "RETURN t1.id, t2.id, rel.note, rel.ts"
    )
    n_res = g.ro_query(next_cypher, {"rid": run_id})
    next_edges = []
    for row in n_res.result_set or []:
        next_edges.append({
            "src": row[0],
            "dst": row[1],
            "note": row[2],
            "ts": row[3],
        })

    return {"tasks": tasks, "next": next_edges}


# --- Actions Lifecycle ---


def record_action(
    tenant: str,
    run_id: str,
    kind: str,
    payload: Dict[str, Any],
) -> str:
    """Creates a proposed action and links (Run)-[:PROPOSED]->(Action)."""
    g = graph_for(tenant)
    action_id = f"act_{uuid.uuid4().hex[:8]}"
    ts = now_ms()

    # Ensure labeled as simulated in payload
    clean_payload = dict(payload)
    clean_payload["simulated"] = True
    payload_str = json.dumps(clean_payload)

    cypher = (
        "MATCH (r:Run {id: $rid}) "
        "CREATE (a:Action { "
        "  id: $aid, run_id: $rid, kind: $kind, payload: $payload, "
        "  status: 'proposed', ts: $ts "
        "}) "
        "CREATE (r)-[:PROPOSED]->(a) "
        "RETURN a.id"
    )
    g.query(cypher, {"rid": run_id, "aid": action_id, "kind": kind, "payload": payload_str, "ts": ts})
    return action_id


def decide_action(
    tenant: str,
    action_id: str,
    decision: str,  # 'approved' or 'rejected'
) -> Dict[str, Any]:
    """Transitions an action from 'proposed' to 'approved' or 'rejected'."""
    if decision not in ("approved", "rejected"):
        raise ValueError(f"Invalid decision '{decision}'. Must be 'approved' or 'rejected'")

    g = graph_for(tenant)
    ts = now_ms()
    cypher = (
        "MATCH (a:Action {id: $aid}) WHERE a.status = 'proposed' "
        "SET a.status = $decision, a.decided_at = $ts "
        "RETURN a.id, a.kind, a.status, a.payload, a.run_id"
    )
    res = g.query(cypher, {"aid": action_id, "decision": decision, "ts": ts})
    if not res.result_set:
        raise ValueError(f"Action '{action_id}' is not in 'proposed' state or does not exist")

    row = res.result_set[0]
    return {
        "id": row[0],
        "kind": row[1],
        "status": row[2],
        "payload": json.loads(row[3]) if row[3] else {},
        "run_id": row[4],
    }


def execute_action(tenant: str, action_id: str) -> Dict[str, Any]:
    """
    Executes an approved action, creates corresponding side-effect node
    (Notification, Ticket, StatusUpdate), links it, and transitions status to 'executed'.
    """
    g = graph_for(tenant)
    ts = now_ms()

    # Fetch action
    fetch_cypher = (
        "MATCH (a:Action {id: $aid}) "
        "RETURN a.id, a.kind, a.status, a.payload, a.run_id"
    )
    res = g.query(fetch_cypher, {"aid": action_id})
    if not res.result_set:
        raise ValueError(f"Action '{action_id}' does not exist")

    aid, kind, status, payload_raw, run_id = res.result_set[0]
    if status != "approved":
        raise ValueError(f"Cannot execute action in status '{status}'. Must be 'approved'")

    payload = json.loads(payload_raw) if payload_raw else {}
    side_effect_id = f"se_{uuid.uuid4().hex[:8]}"

    if kind == "page_person":
        # Create Notification node
        se_cypher = (
            "MATCH (a:Action {id: $aid}) "
            "CREATE (n:Notification { "
            "  id: $seid, target_person: $target, message: $msg, reason: $reason, "
            "  simulated: true, ts: $ts "
            "}) "
            "CREATE (a)-[:EXECUTED_AS]->(n) "
            "SET a.status = 'executed'"
        )
        g.query(
            se_cypher,
            {
                "aid": aid,
                "seid": side_effect_id,
                "target": payload.get("person_id", ""),
                "msg": payload.get("message", ""),
                "reason": payload.get("reason", ""),
                "ts": ts,
            },
        )
    elif kind == "create_ticket":
        # Create Ticket node
        se_cypher = (
            "MATCH (a:Action {id: $aid}) "
            "CREATE (t:Ticket { "
            "  id: $seid, title: $title, body: $body, reason: $reason, "
            "  service_id: $sid, status: 'open', simulated: true, ts: $ts "
            "}) "
            "CREATE (a)-[:EXECUTED_AS]->(t) "
            "SET a.status = 'executed'"
        )
        g.query(
            se_cypher,
            {
                "aid": aid,
                "seid": side_effect_id,
                "title": payload.get("title", ""),
                "body": payload.get("body", ""),
                "reason": payload.get("reason", ""),
                "sid": payload.get("service_id", ""),
                "ts": ts,
            },
        )
    elif kind == "post_status_update":
        # Create StatusUpdate node
        se_cypher = (
            "MATCH (a:Action {id: $aid}) "
            "CREATE (s:StatusUpdate { "
            "  id: $seid, text: $text, audience: $aud, reason: $reason, "
            "  simulated: true, ts: $ts "
            "}) "
            "CREATE (a)-[:EXECUTED_AS]->(s) "
            "SET a.status = 'executed'"
        )
        g.query(
            se_cypher,
            {
                "aid": aid,
                "seid": side_effect_id,
                "text": payload.get("text", ""),
                "aud": payload.get("audience", ""),
                "reason": payload.get("reason", ""),
                "ts": ts,
            },
        )
    else:
        # Generic executed
        g.query(
            "MATCH (a:Action {id: $aid}) SET a.status = 'executed'",
            {"aid": aid},
        )

    return {
        "id": aid,
        "kind": kind,
        "status": "executed",
        "side_effect_id": side_effect_id,
        "payload": payload,
    }
