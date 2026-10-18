import argparse
import sys
import time
from typing import Any

from app.config import settings
from app.db import graph_for
from app.embeddings import embed_texts
from app.schema import ensure_schema
from app.seed.generate import build_dataset


def chunk_list(items: list[Any], size: int = 200):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_tenant(tenant: str, reset: bool = False):
    print(f"\n--- Loading seed data for tenant '{tenant}' (reset={reset}) ---")
    g = graph_for(tenant)

    if reset:
        print(f"Dropping existing graph 'ariadne_{tenant}'...")
        try:
            g.delete()
        except Exception as e:
            print(f"Graph deletion notice: {e}")
        # Re-fetch graph instance
        g = graph_for(tenant)

    print(f"Ensuring schema and indexes for '{tenant}'...")
    ensure_schema(tenant)

    print(f"Generating dataset for '{tenant}'...")
    data = build_dataset(tenant)

    # --- 1. Compute Embeddings ---
    # Incident embeddings: title + summary
    if data["incidents"]:
        inc_texts = [f"{inc['title']}. {inc['summary']}" for inc in data["incidents"]]
        print(f"Embedding {len(inc_texts)} Incidents...")
        inc_vectors = embed_texts(inc_texts, task_type="RETRIEVAL_DOCUMENT")
        for inc, vec in zip(data["incidents"], inc_vectors):
            inc["embedding"] = vec

    # Doc embeddings: title + body
    if data["docs"]:
        doc_texts = [f"{doc['title']}\n{doc['body']}" for doc in data["docs"]]
        print(f"Embedding {len(doc_texts)} Docs...")
        doc_vectors = embed_texts(doc_texts, task_type="RETRIEVAL_DOCUMENT")
        for doc, vec in zip(data["docs"], doc_vectors):
            doc["embedding"] = vec

    # Episode embeddings: goal + summary
    if data["episodes"]:
        epi_texts = [f"{epi['goal']}. {epi['summary']}" for epi in data["episodes"]]
        print(f"Embedding {len(epi_texts)} Episodes...")
        epi_vectors = embed_texts(epi_texts, task_type="RETRIEVAL_DOCUMENT")
        for epi, vec in zip(data["episodes"], epi_vectors):
            epi["embedding"] = vec

    # Fact embeddings: text
    if data["facts"]:
        fct_texts = [fct["text"] for fct in data["facts"]]
        print(f"Embedding {len(fct_texts)} Facts...")
        fct_vectors = embed_texts(fct_texts, task_type="RETRIEVAL_DOCUMENT")
        for fct, vec in zip(data["facts"], fct_vectors):
            fct["embedding"] = vec

    # Procedure embeddings: name + trigger_text
    if data["procedures"]:
        prc_texts = [f"{prc['name']}. {prc['trigger_text']}" for prc in data["procedures"]]
        print(f"Embedding {len(prc_texts)} Procedures...")
        prc_vectors = embed_texts(prc_texts, task_type="RETRIEVAL_DOCUMENT")
        for prc, vec in zip(data["procedures"], prc_vectors):
            prc["embedding"] = vec

    # --- 2. Bulk Insert Nodes (UNWIND batches of 200, MERGE on id) ---
    # Teams
    for chunk in chunk_list(data["teams"]):
        g.query(
            "UNWIND $batch AS item MERGE (t:Team {id: item.id}) SET t.name = item.name",
            {"batch": chunk},
        )

    # Services
    for chunk in chunk_list(data["services"]):
        clean_chunk = [
            {
                "id": s["id"],
                "name": s["name"],
                "kind": s["kind"],
                "tier": s["tier"],
                "description": s["description"],
            }
            for s in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (s:Service {id: item.id}) "
            "SET s.name = item.name, s.kind = item.kind, s.tier = item.tier, s.description = item.description",
            {"batch": clean_chunk},
        )

    # People
    for chunk in chunk_list(data["people"]):
        clean_chunk = [
            {"id": p["id"], "name": p["name"], "role": p["role"], "status": p["status"]}
            for p in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (p:Person {id: item.id}) "
            "SET p.name = item.name, p.role = item.role, p.status = item.status",
            {"batch": clean_chunk},
        )

    # Customers
    for chunk in chunk_list(data["customers"]):
        g.query(
            "UNWIND $batch AS item MERGE (c:Customer {id: item.id}) "
            "SET c.name = item.name, c.plan = item.plan",
            {"batch": chunk},
        )

    # Incidents
    for chunk in chunk_list(data["incidents"]):
        clean_chunk = [
            {
                "id": inc["id"],
                "title": inc["title"],
                "severity": inc["severity"],
                "started_at": inc["started_at"],
                "resolved_at": inc["resolved_at"],
                "summary": inc["summary"],
                "embedding": inc["embedding"],
            }
            for inc in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (i:Incident {id: item.id}) "
            "SET i.title = item.title, i.severity = item.severity, i.started_at = item.started_at, "
            "i.resolved_at = item.resolved_at, i.summary = item.summary, i.embedding = vecf32(item.embedding)",
            {"batch": clean_chunk},
        )

    # Docs
    for chunk in chunk_list(data["docs"]):
        clean_chunk = [
            {
                "id": d["id"],
                "title": d["title"],
                "kind": d["kind"],
                "body": d["body"],
                "embedding": d["embedding"],
            }
            for d in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (d:Doc {id: item.id}) "
            "SET d.title = item.title, d.kind = item.kind, d.body = item.body, d.embedding = vecf32(item.embedding)",
            {"batch": clean_chunk},
        )

    # Decisions
    for chunk in chunk_list(data["decisions"]):
        clean_chunk = [
            {
                "id": dec["id"],
                "title": dec["title"],
                "rationale": dec["rationale"],
                "decided_at": dec["decided_at"],
                "status": dec["status"],
            }
            for dec in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (d:Decision {id: item.id}) "
            "SET d.title = item.title, d.rationale = item.rationale, d.decided_at = item.decided_at, d.status = item.status",
            {"batch": clean_chunk},
        )

    # Threads
    for chunk in chunk_list(data["threads"]):
        clean_chunk = [
            {"id": t["id"], "channel": t["channel"], "summary": t["summary"], "ts": t["ts"]}
            for t in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (t:Thread {id: item.id}) "
            "SET t.channel = item.channel, t.summary = item.summary, t.ts = item.ts",
            {"batch": clean_chunk},
        )

    # Tickets
    for chunk in chunk_list(data["tickets"]):
        clean_chunk = [
            {
                "id": t["id"],
                "title": t["title"],
                "status": t["status"],
                "created_at": t["created_at"],
                "resolved_at": t["resolved_at"],
            }
            for t in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (t:Ticket {id: item.id}) "
            "SET t.title = item.title, t.status = item.status, t.created_at = item.created_at, t.resolved_at = item.resolved_at",
            {"batch": clean_chunk},
        )

    # Memory Facts
    for chunk in chunk_list(data["facts"]):
        clean_chunk = [
            {
                "id": f["id"],
                "subject_id": f["subject_id"],
                "predicate": f["predicate"],
                "text": f["text"],
                "confidence": f["confidence"],
                "valid_from": f["valid_from"],
                "valid_to": f["valid_to"],
                "embedding": f["embedding"],
            }
            for f in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (f:Fact {id: item.id}) "
            "SET f.subject_id = item.subject_id, f.predicate = item.predicate, f.text = item.text, "
            "f.confidence = item.confidence, f.valid_from = item.valid_from, f.valid_to = item.valid_to, "
            "f.embedding = vecf32(item.embedding)",
            {"batch": clean_chunk},
        )

    # Memory Procedures
    for chunk in chunk_list(data["procedures"]):
        clean_chunk = [
            {
                "id": p["id"],
                "name": p["name"],
                "trigger_text": p["trigger_text"],
                "steps": p["steps"],
                "success_count": p["success_count"],
                "fail_count": p["fail_count"],
                "last_used": p["last_used"],
                "embedding": p["embedding"],
            }
            for p in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (p:Procedure {id: item.id}) "
            "SET p.name = item.name, p.trigger_text = item.trigger_text, p.steps = item.steps, "
            "p.success_count = item.success_count, p.fail_count = item.fail_count, p.last_used = item.last_used, "
            "p.embedding = vecf32(item.embedding)",
            {"batch": clean_chunk},
        )

    # Memory Episodes
    for chunk in chunk_list(data["episodes"]):
        clean_chunk = [
            {
                "id": e["id"],
                "run_id": e["run_id"],
                "goal": e["goal"],
                "outcome": e["outcome"],
                "summary": e["summary"],
                "ts": e["ts"],
                "embedding": e["embedding"],
            }
            for e in chunk
        ]
        g.query(
            "UNWIND $batch AS item MERGE (e:Episode {id: item.id}) "
            "SET e.run_id = item.run_id, e.goal = item.goal, e.outcome = item.outcome, "
            "e.summary = item.summary, e.ts = item.ts, e.embedding = vecf32(item.embedding)",
            {"batch": clean_chunk},
        )

    # --- 3. Bulk Insert Edges ---
    # Member_of: (Person)-[:MEMBER_OF]->(Team)
    for chunk in chunk_list(data["member_of"]):
        g.query(
            "UNWIND $batch AS item "
            "MATCH (p:Person {id: item.person_id}), (t:Team {id: item.team_id}) "
            "MERGE (p)-[:MEMBER_OF]->(t)",
            {"batch": chunk},
        )

    # Owns: (Team)-[:OWNS]->(Service)
    for chunk in chunk_list(data["owns"]):
        g.query(
            "UNWIND $batch AS item "
            "MATCH (t:Team {id: item.team_id}), (s:Service {id: item.service_id}) "
            "MERGE (t)-[:OWNS]->(s)",
            {"batch": chunk},
        )

    # Depends_on: (Service)-[:DEPENDS_ON]->(Service)
    for chunk in chunk_list(data["depends_on"]):
        g.query(
            "UNWIND $batch AS item "
            "MATCH (src:Service {id: item.src}), (dst:Service {id: item.dst}) "
            "MERGE (src)-[:DEPENDS_ON]->(dst)",
            {"batch": chunk},
        )

    # Worked_on: (Person)-[:WORKED_ON {commits}]->(Service)
    for chunk in chunk_list(data["worked_on"]):
        g.query(
            "UNWIND $batch AS item "
            "MATCH (p:Person {id: item.person_id}), (s:Service {id: item.service_id}) "
            "MERGE (p)-[r:WORKED_ON]->(s) SET r.commits = item.commits",
            {"batch": chunk},
        )

    # Uses: (Customer)-[:USES]->(Service)
    for chunk in chunk_list(data["uses"]):
        g.query(
            "UNWIND $batch AS item "
            "MATCH (c:Customer {id: item.customer_id}), (s:Service {id: item.service_id}) "
            "MERGE (c)-[:USES]->(s)",
            {"batch": chunk},
        )

    # Doc relations: DOCUMENTS, AUTHORED
    for chunk in chunk_list(data["docs"]):
        g.query(
            "UNWIND $batch AS item "
            "MATCH (d:Doc {id: item.id}), (s:Service {id: item.service_id}) "
            "MERGE (d)-[:DOCUMENTS]->(s)",
            {"batch": chunk},
        )

    # Decision relations: ABOUT, SUPERSEDES, RECORDED_IN, AUTHORED, DISCUSSED_IN
    for dec in data["decisions"]:
        g.query(
            "MATCH (dec:Decision {id: $did}), (s:Service {id: $sid}) MERGE (dec)-[:ABOUT]->(s)",
            {"did": dec["id"], "sid": dec["service_id"]},
        )
        if dec.get("author_id"):
            g.query(
                "MATCH (p:Person {id: $pid}), (dec:Decision {id: $did}) MERGE (p)-[:AUTHORED]->(dec)",
                {"pid": dec["author_id"], "did": dec["id"]},
            )
        if dec.get("doc_id"):
            g.query(
                "MATCH (dec:Decision {id: $did}), (doc:Doc {id: $doc_id}) MERGE (dec)-[:RECORDED_IN]->(doc)",
                {"did": dec["id"], "doc_id": dec["doc_id"]},
            )
        if dec.get("thread_id"):
            g.query(
                "MATCH (dec:Decision {id: $did}), (thr:Thread {id: $tid}) MERGE (dec)-[:DISCUSSED_IN]->(thr)",
                {"did": dec["id"], "tid": dec["thread_id"]},
            )
    # Check SUPERSEDES for hero decisions: dec_029 SUPERSEDES dec_017
    if tenant == "northwind":
        g.query("MATCH (d2:Decision {id: 'dec_029'}), (d1:Decision {id: 'dec_017'}) MERGE (d2)-[:SUPERSEDES]->(d1)")

    # Thread relations: ABOUT Service
    for thr in data["threads"]:
        if thr.get("service_id"):
            g.query(
                "MATCH (t:Thread {id: $tid}), (s:Service {id: $sid}) MERGE (t)-[:ABOUT]->(s)",
                {"tid": thr["id"], "sid": thr["service_id"]},
            )

    # Incident relations: AFFECTED, ROOT_CAUSE_IN, RESOLVED, RESOLVED_WITH
    for inc in data["incidents"]:
        for aff in inc.get("affected", []):
            g.query(
                "MATCH (i:Incident {id: $iid}), (s:Service {id: $sid}) MERGE (i)-[:AFFECTED]->(s)",
                {"iid": inc["id"], "sid": aff},
            )
        if inc.get("root_cause_in"):
            g.query(
                "MATCH (i:Incident {id: $iid}), (s:Service {id: $sid}) MERGE (i)-[:ROOT_CAUSE_IN]->(s)",
                {"iid": inc["id"], "sid": inc["root_cause_in"]},
            )
        if inc.get("resolved_by"):
            g.query(
                "MATCH (p:Person {id: $pid}), (i:Incident {id: $iid}) MERGE (p)-[:RESOLVED]->(i)",
                {"pid": inc["resolved_by"], "iid": inc["id"]},
            )
        if inc.get("resolved_with"):
            g.query(
                "MATCH (i:Incident {id: $iid}), (d:Doc {id: $did}) MERGE (i)-[:RESOLVED_WITH]->(d)",
                {"iid": inc["id"], "did": inc["resolved_with"]},
            )

    # Ticket relations: RAISED, ABOUT, RELATES_TO, ASSIGNED_TO
    for tkt in data["tickets"]:
        if tkt.get("customer_id"):
            g.query(
                "MATCH (c:Customer {id: $cid}), (t:Ticket {id: $tid}) MERGE (c)-[:RAISED]->(t)",
                {"cid": tkt["customer_id"], "tid": tkt["id"]},
            )
        if tkt.get("service_id"):
            g.query(
                "MATCH (t:Ticket {id: $tid}), (s:Service {id: $sid}) MERGE (t)-[:ABOUT]->(s)",
                {"tid": tkt["id"], "sid": tkt["service_id"]},
            )
        if tkt.get("assigned_to"):
            g.query(
                "MATCH (t:Ticket {id: $tid}), (p:Person {id: $pid}) MERGE (t)-[:ASSIGNED_TO]->(p)",
                {"tid": tkt["id"], "pid": tkt["assigned_to"]},
            )
        if tkt.get("relates_to_incident"):
            g.query(
                "MATCH (t:Ticket {id: $tid}), (i:Incident {id: $iid}) MERGE (t)-[:RELATES_TO]->(i)",
                {"tid": tkt["id"], "iid": tkt["relates_to_incident"]},
            )

    # Memory relations: Fact ABOUT, Procedure APPLIES_TO, Episode ABOUT / USED / PRODUCED
    for fct in data["facts"]:
        g.query(
            "MATCH (f:Fact {id: $fid}), (s:Service {id: $sid}) MERGE (f)-[:ABOUT]->(s)",
            {"fid": fct["id"], "sid": fct["subject_id"]},
        )
    for prc in data["procedures"]:
        g.query(
            "MATCH (p:Procedure {id: $pid}), (s:Service {id: $sid}) MERGE (p)-[:APPLIES_TO]->(s)",
            {"pid": prc["id"], "sid": prc["service_id"]},
        )
    for epi in data["episodes"]:
        if epi.get("service_id"):
            g.query(
                "MATCH (e:Episode {id: $eid}), (s:Service {id: $sid}) MERGE (e)-[:ABOUT]->(s)",
                {"eid": epi["id"], "sid": epi["service_id"]},
            )
        if epi.get("incident_id"):
            g.query(
                "MATCH (e:Episode {id: $eid}), (i:Incident {id: $iid}) MERGE (e)-[:ABOUT]->(i)",
                {"eid": epi["id"], "iid": epi["incident_id"]},
            )
        if epi.get("procedure_id"):
            g.query(
                "MATCH (e:Episode {id: $eid}), (p:Procedure {id: $pid}) MERGE (e)-[:USED]->(p)",
                {"eid": epi["id"], "pid": epi["procedure_id"]},
            )
        if epi.get("produced_fact_id"):
            g.query(
                "MATCH (e:Episode {id: $eid}), (f:Fact {id: $fid}) MERGE (e)-[:PRODUCED]->(f)",
                {"eid": epi["id"], "fid": epi["produced_fact_id"]},
            )

    # --- 4. Report Counts ---
    print(f"\nSummary of loaded data for tenant '{tenant}':")
    node_labels = ["Team", "Service", "Person", "Customer", "Doc", "Incident", "Decision", "Thread", "Ticket", "Fact", "Procedure", "Episode"]
    for lbl in node_labels:
        cnt = g.ro_query(f"MATCH (n:{lbl}) RETURN count(n)").result_set[0][0]
        if cnt > 0:
            print(f"  Node :{lbl:12} -> {cnt}")

    rel_res = g.ro_query("MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC")
    for row in rel_res.result_set:
        print(f"  Edge [:{row[0]:14}] -> {row[1]}")
    total_nodes = g.ro_query("MATCH (n) RETURN count(n)").result_set[0][0]
    total_edges = g.ro_query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    print(f"Total: {total_nodes} nodes, {total_edges} edges in ariadne_{tenant}.\n")


def main():
    parser = argparse.ArgumentParser(description="Load seed dataset into FalkorDB")
    parser.add_argument("--tenant", choices=["northwind", "acme"], default="northwind")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate graph")
    args = parser.parse_args()

    load_tenant(args.tenant, reset=args.reset)


if __name__ == "__main__":
    main()
