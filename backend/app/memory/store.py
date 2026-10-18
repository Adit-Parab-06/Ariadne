import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.db import graph_for
from app.embeddings import embed_texts
from app.tools.evidence import Evidence


def now_ms() -> int:
    return int(time.time() * 1000)


def write_episode(
    tenant: str,
    run_id: str,
    goal: str,
    outcome: str,
    summary: str,
    service_ids: List[str],
    incident_ids: List[str],
    procedure_id: Optional[str] = None,
    fact_ids: Tuple[str, ...] = (),
) -> str:
    """
    Creates an Episode node with vector embedding and links ABOUT, USED, and PRODUCED edges.
    """
    g = graph_for(tenant)
    epi_id = f"epi_{uuid.uuid4().hex[:8]}"
    ts = now_ms()

    # Generate embedding
    embed_input = f"{goal}. {summary}"
    vectors = embed_texts([embed_input], task_type="RETRIEVAL_DOCUMENT")
    vec = vectors[0]

    # 1. Create Episode node
    cypher_create = (
        "CREATE (e:Episode { "
        "  id: $id, run_id: $run_id, goal: $goal, outcome: $outcome, "
        "  summary: $summary, ts: $ts, embedding: vecf32($vec) "
        "})"
    )
    g.query(
        cypher_create,
        {
            "id": epi_id,
            "run_id": run_id,
            "goal": goal,
            "outcome": outcome,
            "summary": summary,
            "ts": ts,
            "vec": vec,
        },
    )

    # 2. Link ABOUT services
    if service_ids:
        g.query(
            "MATCH (e:Episode {id: $eid}) "
            "UNWIND $sids AS sid "
            "MATCH (s:Service {id: sid}) "
            "MERGE (e)-[:ABOUT]->(s)",
            {"eid": epi_id, "sids": list(service_ids)},
        )

    # 3. Link ABOUT incidents
    if incident_ids:
        g.query(
            "MATCH (e:Episode {id: $eid}) "
            "UNWIND $iids AS iid "
            "MATCH (i:Incident {id: iid}) "
            "MERGE (e)-[:ABOUT]->(i)",
            {"eid": epi_id, "iids": list(incident_ids)},
        )

    # 4. Link USED procedure
    if procedure_id:
        g.query(
            "MATCH (e:Episode {id: $eid}), (p:Procedure {id: $pid}) "
            "MERGE (e)-[:USED]->(p)",
            {"eid": epi_id, "pid": procedure_id},
        )

    # 5. Link PRODUCED facts
    if fact_ids:
        g.query(
            "MATCH (e:Episode {id: $eid}) "
            "UNWIND $fids AS fid "
            "MATCH (f:Fact {id: fid}) "
            "MERGE (e)-[:PRODUCED]->(f)",
            {"eid": epi_id, "fids": list(fact_ids)},
        )

    return epi_id


def upsert_fact(
    tenant: str,
    subject_id: str,
    predicate: str,
    text: str,
    confidence: float,
    source_episode_id: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Upserts a semantic fact. If a current fact (valid_to = 0) exists for subject+predicate,
    closes it and creates the new fact linking (new)-[:SUPERSEDES]->(old) in ONE query.
    Never deletes old facts. Returns (new_id, superseded_id or None).
    """
    g = graph_for(tenant)
    new_id = f"fct_{uuid.uuid4().hex[:8]}"
    ts = now_ms()

    vectors = embed_texts([text], task_type="RETRIEVAL_DOCUMENT")
    vec = vectors[0]

    # Find existing current fact
    find_cypher = (
        "MATCH (f:Fact {subject_id: $sid, predicate: $pred, valid_to: 0}) "
        "RETURN f.id LIMIT 1"
    )
    res = g.query(find_cypher, {"sid": subject_id, "pred": predicate})
    old_id = res.result_set[0][0] if res.result_set else None

    if old_id:
        # Atomic close and link in ONE query
        supersede_cypher = (
            "MATCH (old:Fact {id: $old_id}), (s:Service {id: $sid}) "
            "SET old.valid_to = $now "
            "CREATE (new:Fact { "
            "  id: $new_id, subject_id: $sid, predicate: $pred, text: $text, "
            "  confidence: $conf, valid_from: $now, valid_to: 0, embedding: vecf32($vec) "
            "}) "
            "CREATE (new)-[:SUPERSEDES]->(old) "
            "CREATE (new)-[:ABOUT]->(s)"
        )
        g.query(
            supersede_cypher,
            {
                "old_id": old_id,
                "sid": subject_id,
                "now": ts,
                "new_id": new_id,
                "pred": predicate,
                "text": text,
                "conf": float(confidence),
                "vec": vec,
            },
        )
    else:
        create_cypher = (
            "MATCH (s:Service {id: $sid}) "
            "CREATE (new:Fact { "
            "  id: $new_id, subject_id: $sid, predicate: $pred, text: $text, "
            "  confidence: $conf, valid_from: $now, valid_to: 0, embedding: vecf32($vec) "
            "}) "
            "CREATE (new)-[:ABOUT]->(s)"
        )
        g.query(
            create_cypher,
            {
                "sid": subject_id,
                "new_id": new_id,
                "pred": predicate,
                "text": text,
                "conf": float(confidence),
                "now": ts,
                "vec": vec,
            },
        )

    if source_episode_id:
        g.query(
            "MATCH (e:Episode {id: $eid}), (f:Fact {id: $fid}) MERGE (e)-[:PRODUCED]->(f)",
            {"eid": source_episode_id, "fid": new_id},
        )

    return new_id, old_id


def current_facts(tenant: str, service_ids: List[str]) -> List[Dict[str, Any]]:
    """Returns active facts (valid_to = 0) for given service IDs using Fact.subject_id index."""
    if not service_ids:
        return []
    g = graph_for(tenant)
    cypher = (
        "UNWIND $sids AS sid "
        "MATCH (f:Fact {subject_id: sid, valid_to: 0}) "
        "RETURN f.id, f.subject_id, f.predicate, f.text, f.confidence, f.valid_from, f.valid_to"
    )
    res = g.ro_query(cypher, {"sids": list(service_ids)})
    facts = []
    for row in res.result_set or []:
        facts.append({
            "id": row[0],
            "subject_id": row[1],
            "predicate": row[2],
            "text": row[3],
            "confidence": row[4],
            "valid_from": row[5],
            "valid_to": row[6],
        })
    return facts


def create_procedure(
    tenant: str,
    name: str,
    trigger_text: str,
    steps: Any,
    service_ids: List[str],
) -> str:
    """Creates a procedural memory node with steps JSON and APPLIES_TO edges."""
    g = graph_for(tenant)
    prc_id = f"prc_{uuid.uuid4().hex[:8]}"
    ts = now_ms()

    steps_json = json.dumps(steps) if isinstance(steps, (list, dict)) else str(steps)
    embed_input = f"{name}. {trigger_text}"
    vectors = embed_texts([embed_input], task_type="RETRIEVAL_DOCUMENT")
    vec = vectors[0]

    cypher = (
        "CREATE (p:Procedure { "
        "  id: $id, name: $name, trigger_text: $trigger, steps: $steps, "
        "  success_count: 0, fail_count: 0, last_used: $ts, embedding: vecf32($vec) "
        "})"
    )
    g.query(
        cypher,
        {
            "id": prc_id,
            "name": name,
            "trigger": trigger_text,
            "steps": steps_json,
            "ts": ts,
            "vec": vec,
        },
    )

    if service_ids:
        g.query(
            "MATCH (p:Procedure {id: $pid}) "
            "UNWIND $sids AS sid "
            "MATCH (s:Service {id: sid}) "
            "MERGE (p)-[:APPLIES_TO]->(s)",
            {"pid": prc_id, "sids": list(service_ids)},
        )

    return prc_id


def bump_procedure(tenant: str, procedure_id: str, success: bool) -> None:
    """Increments success_count or fail_count and updates last_used."""
    g = graph_for(tenant)
    ts = now_ms()
    cypher = (
        "MATCH (p:Procedure {id: $pid}) "
        "SET p.success_count = p.success_count + (CASE WHEN $succ THEN 1 ELSE 0 END), "
        "    p.fail_count = p.fail_count + (CASE WHEN $succ THEN 0 ELSE 1 END), "
        "    p.last_used = $ts"
    )
    g.query(cypher, {"pid": procedure_id, "succ": success, "ts": ts})


def recall(
    tenant: str,
    text: str,
    service_ids: Optional[List[str]] = None,
    k: int = 3,
) -> Dict[str, Any]:
    """
    Recalls episodic, semantic, and procedural memories:
    - Episodes: vector search with k*3 candidates, reranked by cosine similarity + graph overlap bonus.
    - Facts: current_facts for service_ids.
    - Procedures: linked by APPLIES_TO to service_ids plus top vector match.
    Returns memories with evidence graph.
    """
    g = graph_for(tenant)
    sids = service_ids or []
    evidence = Evidence()

    vectors = embed_texts([text], task_type="RETRIEVAL_QUERY")
    query_vec = vectors[0]

    # --- 1. Episodes ---
    cand_k = max(k * 3, 5)
    epi_cypher = (
        "CALL db.idx.vector.queryNodes('Episode', 'embedding', $k, vecf32($vec)) "
        "YIELD node, score "
        "RETURN node.id, node.run_id, node.goal, node.outcome, node.summary, node.ts, score"
    )
    try:
        epi_res = g.query(epi_cypher, {"k": cand_k, "vec": query_vec})
        epi_rows = epi_res.result_set or []
    except Exception:
        epi_rows = []

    ranked_episodes = []
    for row in epi_rows:
        eid, run_id, goal, outcome, summary, ts, score = row
        # PROBE_RESULTS confirmed score is cosine distance: 0 is exact match, 1 is orthogonal
        dist = float(score)
        similarity = 1.0 - min(max(dist, 0.0), 1.0)

        # Check graph overlap with target services
        overlap_bonus = 0.0
        if sids:
            overlap_cypher = (
                "MATCH (e:Episode {id: $eid})-[:ABOUT]->(s:Service) "
                "WHERE s.id IN $sids "
                "RETURN count(s)"
            )
            overlap_res = g.ro_query(overlap_cypher, {"eid": eid, "sids": sids})
            if overlap_res.result_set and overlap_res.result_set[0][0] > 0:
                overlap_bonus = 0.25

        final_score = similarity + overlap_bonus
        ranked_episodes.append({
            "id": eid,
            "run_id": run_id,
            "goal": goal,
            "outcome": outcome,
            "summary": summary,
            "ts": ts,
            "similarity": round(similarity, 4),
            "final_score": round(final_score, 4),
        })

    ranked_episodes.sort(key=lambda e: e["final_score"], reverse=True)
    top_episodes = ranked_episodes[:k]

    for ep in top_episodes:
        evidence.add_node(ep["id"], "Episode", ep["goal"][:40])
        # Add ABOUT edges for evidence
        about_res = g.ro_query(
            "MATCH (e:Episode {id: $eid})-[:ABOUT]->(n) RETURN n.id, labels(n)[0], coalesce(n.name, n.title)",
            {"eid": ep["id"]},
        )
        for arow in about_res.result_set or []:
            evidence.add_node(arow[0], arow[1], str(arow[2]))
            evidence.add_edge(ep["id"], "ABOUT", arow[0])

    # --- 2. Facts ---
    facts = current_facts(tenant, sids)
    for f in facts:
        evidence.add_node(f["id"], "Fact", f["text"])
        evidence.add_edge(f["id"], "ABOUT", f["subject_id"])

    # --- 3. Procedures ---
    proc_map: Dict[str, Dict[str, Any]] = {}
    if sids:
        # Graph-linked procedures
        p_res = g.ro_query(
            "MATCH (p:Procedure)-[:APPLIES_TO]->(s:Service) "
            "WHERE s.id IN $sids "
            "RETURN p.id, p.name, p.trigger_text, p.steps, p.success_count, p.fail_count, p.last_used, s.id",
            {"sids": sids},
        )
        for prow in p_res.result_set or []:
            pid = prow[0]
            if pid not in proc_map:
                proc_map[pid] = {
                    "id": pid,
                    "name": prow[1],
                    "trigger_text": prow[2],
                    "steps": prow[3],
                    "success_count": prow[4],
                    "fail_count": prow[5],
                    "last_used": prow[6],
                }
            evidence.add_node(pid, "Procedure", prow[1])
            evidence.add_edge(pid, "APPLIES_TO", prow[7])

    # Best vector procedure match
    try:
        p_vec_res = g.query(
            "CALL db.idx.vector.queryNodes('Procedure', 'embedding', 1, vecf32($vec)) "
            "YIELD node, score "
            "RETURN node.id, node.name, node.trigger_text, node.steps, node.success_count, node.fail_count, node.last_used",
            {"vec": query_vec},
        )
        for prow in p_vec_res.result_set or []:
            pid = prow[0]
            if pid not in proc_map:
                proc_map[pid] = {
                    "id": pid,
                    "name": prow[1],
                    "trigger_text": prow[2],
                    "steps": prow[3],
                    "success_count": prow[4],
                    "fail_count": prow[5],
                    "last_used": prow[6],
                }
                evidence.add_node(pid, "Procedure", prow[1])
    except Exception:
        pass

    procedures = list(proc_map.values())

    return {
        "episodes": top_episodes,
        "facts": facts,
        "procedures": procedures,
        "evidence": evidence,
    }


# --- Persistent Conversations ---


def start_conversation(tenant: str) -> str:
    """Initializes a new persistent conversation node."""
    g = graph_for(tenant)
    cid = f"cnv_{uuid.uuid4().hex[:8]}"
    ts = now_ms()
    cypher = "CREATE (c:Conversation {id: $cid, started_at: $ts}) RETURN c.id"
    g.query(cypher, {"cid": cid, "ts": ts})
    return cid


def add_message(tenant: str, conversation_id: str, role: str, text: str) -> str:
    """Adds a message to an existing conversation with monotonic ordering."""
    g = graph_for(tenant)
    mid = f"msg_{uuid.uuid4().hex[:8]}"
    ts = now_ms()

    # Get current index
    idx_res = g.query(
        "MATCH (c:Conversation {id: $cid})-[:HAS_MSG]->(m:Msg) RETURN count(m)",
        {"cid": conversation_id},
    )
    idx = idx_res.result_set[0][0] if idx_res.result_set else 0

    cypher = (
        "MATCH (c:Conversation {id: $cid}) "
        "CREATE (m:Msg {id: $mid, idx: $idx, role: $role, text: $text, ts: $ts}) "
        "CREATE (c)-[:HAS_MSG]->(m) "
        "RETURN m.id"
    )
    g.query(cypher, {"cid": conversation_id, "mid": mid, "idx": idx, "role": role, "text": text, "ts": ts})
    return mid


def get_conversation(tenant: str, conversation_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves conversation messages in chronological sequence."""
    g = graph_for(tenant)
    cypher = (
        "MATCH (c:Conversation {id: $cid})-[:HAS_MSG]->(m:Msg) "
        "RETURN m.id, m.idx, m.role, m.text, m.ts "
        "ORDER BY m.idx ASC LIMIT $lim"
    )
    res = g.ro_query(cypher, {"cid": conversation_id, "lim": limit})
    msgs = []
    for row in res.result_set or []:
        msgs.append({
            "id": row[0],
            "idx": row[1],
            "role": row[2],
            "text": row[3],
            "ts": row[4],
        })
    return msgs
