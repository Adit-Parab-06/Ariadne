import json
import pytest
from app.db import graph_for
from app.memory.consolidate import consolidate
from app.memory.store import (
    add_message,
    bump_procedure,
    current_facts,
    get_conversation,
    recall,
    start_conversation,
    upsert_fact,
    write_episode,
)
from app.seed.load import load_tenant
from app.tools.memory import similar_incidents


@pytest.fixture(scope="module", autouse=True)
def restore_pristine_seed():
    """Runs tests and reloads pristine Northwind seed data at teardown."""
    yield
    load_tenant("northwind", reset=True)


def test_similar_incidents_hero():
    res = similar_incidents(
        "northwind",
        "payments-api p99 latency is 4.2s and 5xx errors at 8%",
        service_ids=["svc_payments_api"],
        k=3,
    )
    incidents = res.data["incidents"]
    assert len(incidents) > 0
    # inc_2041 must be returned first due to vector similarity + affected service bonus
    assert incidents[0]["id"] == "inc_2041", f"Expected inc_2041 first, got {incidents[0]['id']}"
    assert incidents[0]["resolved_by"]["id"] == "per_priya_nair"
    assert incidents[0]["resolved_with_doc"]["id"] == "doc_rb_ledger_pool"


def test_recall_memory_seed():
    res = recall("northwind", "latency and 5xx connection pool saturation", service_ids=["svc_ledger_db"], k=3)
    episode_ids = [e["id"] for e in res["episodes"]]
    proc_ids = [p["id"] for p in res["procedures"]]
    fact_ids = [f["id"] for f in res["facts"]]

    assert "epi_2041" in episode_ids
    assert "prc_ledger_pool" in proc_ids
    assert "fct_ledger_pgb_200" in fact_ids


def test_upsert_fact_supersedes():
    g = graph_for("northwind")

    # Upsert a new fact for svc_ledger_db / pgbouncer_max_client_conn
    new_id, superseded_id = upsert_fact(
        "northwind",
        subject_id="svc_ledger_db",
        predicate="pgbouncer_max_client_conn",
        text="ledger-db pgbouncer max_client_conn is 350",
        confidence=0.99,
    )

    assert superseded_id == "fct_ledger_pgb_200"

    # Verify old fact is closed (valid_to > 0)
    res_old = g.query("MATCH (f:Fact {id: 'fct_ledger_pgb_200'}) RETURN f.valid_to")
    assert res_old.result_set and res_old.result_set[0][0] > 0

    # Verify new fact is active (valid_to = 0)
    res_new = g.query("MATCH (f:Fact {id: $id}) RETURN f.valid_to", {"id": new_id})
    assert res_new.result_set and res_new.result_set[0][0] == 0

    # Verify SUPERSEDES edge exists: (new)-[:SUPERSEDES]->(old)
    res_edge = g.query(
        "MATCH (n:Fact {id: $nid})-[:SUPERSEDES]->(o:Fact {id: 'fct_ledger_pgb_200'}) RETURN count(*)",
        {"nid": new_id},
    )
    assert res_edge.result_set[0][0] == 1

    # Verify current_facts returns only the new active fact
    active = current_facts("northwind", ["svc_ledger_db"])
    pgb_facts = [f for f in active if f["predicate"] == "pgbouncer_max_client_conn"]
    assert len(pgb_facts) == 1
    assert pgb_facts[0]["id"] == new_id


def test_bump_procedure():
    g = graph_for("northwind")
    init_res = g.query("MATCH (p:Procedure {id: 'prc_ledger_pool'}) RETURN p.success_count")
    init_count = init_res.result_set[0][0]

    bump_procedure("northwind", "prc_ledger_pool", success=True)

    after_res = g.query("MATCH (p:Procedure {id: 'prc_ledger_pool'}) RETURN p.success_count")
    after_count = after_res.result_set[0][0]
    assert after_count == init_count + 1


def test_tenant_isolation():
    # Write a unique episode in Northwind
    test_run_id = "run_isolation_test_01"
    epi_id = write_episode(
        tenant="northwind",
        run_id=test_run_id,
        goal="Secret confidential operation",
        outcome="success",
        summary="Classified details strictly in Northwind",
        service_ids=["svc_ledger_db"],
        incident_ids=[],
    )

    # Recall in Acme
    acme_recall = recall("acme", "Secret confidential operation", k=5)
    acme_epi_ids = [e["id"] for e in acme_recall["episodes"]]
    assert epi_id not in acme_epi_ids
    assert len(acme_epi_ids) == 0  # Acme has no seed episodes


def test_conversation_persistence():
    cid = start_conversation("northwind")
    m1 = add_message("northwind", cid, "user", "What is the status of payments?")
    m2 = add_message("northwind", cid, "assistant", "Payments API latency is elevated.")

    msgs = get_conversation("northwind", cid, limit=10)
    assert len(msgs) == 2
    assert msgs[0]["id"] == m1
    assert msgs[0]["idx"] == 0
    assert msgs[0]["role"] == "user"
    assert msgs[1]["id"] == m2
    assert msgs[1]["idx"] == 1
    assert msgs[1]["role"] == "assistant"


def test_consolidate_stubbed_llm():
    def fake_llm(sys_inst: str, prompt: str) -> str:
        return json.dumps({
            "episode_summary": "Resolved connection pool saturation by increasing pgbouncer connections",
            "outcome": "success",
            "fact_updates": [
                {
                    "service_id": "svc_ledger_db",
                    "predicate": "pgbouncer_max_client_conn",
                    "text": "ledger-db pgbouncer max_client_conn is 500",
                }
            ],
            "procedure": {
                "reuse_id": "prc_ledger_pool",
                "name": "Ledger pool saturation response",
                "trigger_text": "payments-api latency spike and elevated 5xx errors",
                "steps": [
                    "Inspect pgbouncer pools",
                    "Raise connection limit",
                    "Reload pgbouncer",
                    "Verify latency recovery",
                ],
            },
        })

    written = consolidate(
        tenant="northwind",
        run_id="run_cons_test",
        resolution_note="Root cause PgBouncer pool saturated. Raised to 500.",
        run_summary="Scout identified pool saturation; Responder applied configuration.",
        llm_fn=fake_llm,
    )

    labels = [w["label"] for w in written]
    assert "Episode" in labels
    assert "Fact" in labels
    assert "Procedure" in labels

    assert sum(1 for w in written if w["label"] == "Episode") == 1
    assert sum(1 for w in written if w["label"] == "Fact") == 1
    assert sum(1 for w in written if w["label"] == "Procedure") == 1
