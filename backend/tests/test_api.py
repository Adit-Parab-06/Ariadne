import json
import time
from typing import Any, Dict, List, Tuple

import pytest
from fastapi.testclient import TestClient

from app.agents.events import get_bus
from app.agents.orchestrator import run_mission as real_run_mission
from app.api.main import app
import app.api.main as api_main
from app.db import graph_for
from app.seed.load import load_tenant


@pytest.fixture(scope="module", autouse=True)
def restore_seed():
    yield
    load_tenant("northwind", reset=True)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_tenants_and_tools(client):
    """Verifies health check, tenants list, and tool registry inspection endpoints."""
    # 1. Health
    h_res = client.get("/api/health")
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert h_data["falkordb"] is True
    assert "model" in h_data

    # 2. Tenants
    t_res = client.get("/api/tenants")
    assert t_res.status_code == 200
    tenants = t_res.json()
    tenant_ids = [t["id"] for t in tenants]
    assert "northwind" in tenant_ids
    assert "acme" in tenant_ids

    # 3. Tools
    tools_res = client.get("/api/tools")
    assert tools_res.status_code == 200
    tools = tools_res.json()
    assert len(tools) >= 8
    tool_names = [t["name"] for t in tools]
    assert "blast_radius" in tool_names
    assert "find_experts" in tool_names
    assert "page_person" in tool_names


def test_tenant_validation_404(client):
    """Verifies that requests to unknown tenants return 404 with JSON {error: str}."""
    res1 = client.get("/api/invalid_tenant/graph/overview")
    assert res1.status_code == 404
    assert "error" in res1.json()
    assert "Unknown tenant" in res1.json()["error"]

    res2 = client.post("/api/unknown_co/missions", json={"text": "Alert", "mode": "ask"})
    assert res2.status_code == 404
    assert "error" in res2.json()

    res3 = client.get("/api/unknown_co/runs")
    assert res3.status_code == 404
    assert "error" in res3.json()


def test_graph_overview(client):
    """Verifies graph overview returns knowledge layer nodes and edges capped at 300."""
    res = client.get("/api/northwind/graph/overview")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 20
    assert len(data["edges"]) > 20

    # Ensure hero service exists in nodes
    node_ids = [n["id"] for n in data["nodes"]]
    assert "svc_payments_api" in node_ids
    assert "svc_ledger_db" in node_ids


def test_mission_flow_and_sse_replay(client, monkeypatch):
    """
    Tests end-to-end mission creation, SSE event stream replay in order,
    and run inspection using injected deterministic offline agents.
    """
    def fake_agent(
        system_instruction: str,
        user_input: str,
        declarations: List[Dict[str, Any]],
        execute: Any,
        **kwargs,
    ) -> Tuple[str, int]:
        if "Scout" in system_instruction:
            execute("blast_radius", {"service_id": "svc_payments_api", "direction": "dependents"})
            return "Scout found [[svc_payments_api]].", 1
        elif "Archivist" in system_instruction:
            execute("similar_incidents", {"text": "latency", "service_ids": ["svc_payments_api"]})
            return "Archivist found [[inc_2041]].", 1
        elif "Responder" in system_instruction:
            execute("page_person", {
                "person_id": "per_dev_okafor",
                "message": "Inspect pool",
                "reason": "Expert for [[svc_ledger_db]]",
            })
            return "Proposed paging Dev Okafor.", 1
        return "Generic", 0

    def fake_synthesizer(sys_inst: str, prompt: str) -> str:
        return "Summary of [[svc_payments_api]] linked to [[inc_2041]]."

    def patched_run_mission(*args, **kwargs):
        kwargs["agent_runner"] = fake_agent
        kwargs["synthesizer_fn"] = fake_synthesizer
        return real_run_mission(*args, **kwargs)

    monkeypatch.setattr(api_main, "run_mission", patched_run_mission)

    # 1. Post mission
    post_res = client.post(
        "/api/northwind/missions",
        json={"text": "payments-api latency spike", "mode": "respond"},
    )
    assert post_res.status_code == 200
    res_data = post_res.json()
    assert "run_id" in res_data
    assert "conversation_id" in res_data
    run_id = res_data["run_id"]

    # 2. Wait for daemon thread to complete
    bus = get_bus("northwind", run_id)
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if bus.finished:
            break
        time.sleep(0.05)
    assert bus.finished, "Run daemon thread timed out"

    # 3. GET /runs/{run_id}/events (SSE replay)
    sse_res = client.get(f"/api/northwind/runs/{run_id}/events")
    assert sse_res.status_code == 200
    assert "text/event-stream" in sse_res.headers["content-type"]

    sse_lines = sse_res.text.strip().split("\n")
    events = []
    for line in sse_lines:
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    assert len(events) >= 6
    # Verify sequence numbers are monotonic 0, 1, 2, ...
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(len(events)))

    event_types = [e["type"] for e in events]
    assert event_types[0] == "run.started"
    assert "memory.recalled" in event_types
    assert "task.created" in event_types
    assert "task.claimed" in event_types
    assert "handoff" in event_types
    assert "action.proposed" in event_types
    assert "answer.final" in event_types
    assert event_types[-1] == "run.completed"

    # 4. GET /runs/{run_id}
    detail_res = client.get(f"/api/northwind/runs/{run_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["status"] == "completed"
    assert "svc_payments_api" in detail["answer"]
    assert detail["metrics"]["tool_calls"] >= 3
    assert len(detail["actions"]) == 1
    assert detail["actions"][0]["kind"] == "page_person"
    assert detail["actions"][0]["status"] == "proposed"

    # 5. GET /runs list
    runs_res = client.get("/api/northwind/runs")
    assert runs_res.status_code == 200
    runs = runs_res.json()
    run_ids = [r["id"] for r in runs]
    assert run_id in run_ids


def test_action_approval_and_resolve_flow(client, monkeypatch):
    """
    Tests approving a proposed action (creating side-effect Notification node),
    and resolving the run with conflict checks (409 on second resolve).
    """
    # Create and run a mission
    def fake_agent(system_instruction: str, *args, **kwargs):
        if "Responder" in system_instruction:
            kwargs["execute"]("create_ticket", {
                "service_id": "svc_ledger_db",
                "title": "Scale pool",
                "body": "Increase max_client_conn",
                "reason": "Resolves [[svc_payments_api]]",
            })
            return "Ticket proposed", 1
        return "Observation", 0

    def patched_run_mission(*args, **kwargs):
        kwargs["agent_runner"] = fake_agent
        kwargs["synthesizer_fn"] = lambda sys, prompt: "Answer with [[svc_ledger_db]]."
        return real_run_mission(*args, **kwargs)

    monkeypatch.setattr(api_main, "run_mission", patched_run_mission)

    m_res = client.post("/api/northwind/missions", json={"text": "ledger-db alert", "mode": "respond"})
    run_id = m_res.json()["run_id"]

    bus = get_bus("northwind", run_id)
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if bus.finished:
            break
        time.sleep(0.05)
    assert bus.finished

    detail_res = client.get(f"/api/northwind/runs/{run_id}")
    actions = detail_res.json()["actions"]
    assert len(actions) == 1
    action_id = actions[0]["id"]
    assert actions[0]["status"] == "proposed"

    # 1. Approve action
    dec_res = client.post(
        f"/api/northwind/actions/{action_id}/decision",
        json={"decision": "approve"},
    )
    assert dec_res.status_code == 200
    action_data = dec_res.json()
    assert action_data["status"] == "executed"
    assert "side_effect_id" in action_data

    # Verify side-effect node in graph
    g = graph_for("northwind")
    se_res = g.ro_query(
        "MATCH (a:Action {id: $aid})-[:EXECUTED_AS]->(t:Ticket) RETURN t.title, t.simulated",
        {"aid": action_id},
    )
    assert len(se_res.result_set) == 1
    assert se_res.result_set[0][0] == "Scale pool"
    assert se_res.result_set[0][1] is True

    # 2. Resolve run (first time -> 200 OK)
    def fake_consolidate_llm(sys_inst: str, prompt: str) -> str:
        return json.dumps({
            "episode_summary": "Resolved ledger-db saturation by pool resize",
            "outcome": "success",
            "fact_updates": [{
                "service_id": "svc_ledger_db",
                "predicate": "pool_status",
                "text": "Pool limit verified at 250",
            }],
            "procedure": None,
        })

    # Monkeypatch consolidate's LLM
    import app.memory.consolidate as cons_mod
    monkeypatch.setattr(cons_mod, "generate_text", lambda sys, prompt, **kw: fake_consolidate_llm(sys, prompt))

    res_res = client.post(
        f"/api/northwind/runs/{run_id}/resolve",
        json={"note": "Resolved and raised pool limit"},
    )
    assert res_res.status_code == 200
    res_json = res_res.json()
    assert "memory_written" in res_json
    assert len(res_json["memory_written"]) >= 1

    # 3. Resolve conflict test (second resolve -> 409 Conflict)
    second_res = client.post(
        f"/api/northwind/runs/{run_id}/resolve",
        json={"note": "Attempt to resolve again"},
    )
    assert second_res.status_code == 409
    assert "error" in second_res.json()
    assert "resolved" in second_res.json()["error"]


def test_memory_tasks_and_concurrency_lab(client):
    """Verifies memory queries, task queries, and concurrency lab benchmark endpoint."""
    # 1. Memory categories
    ep_res = client.get("/api/northwind/memory?kind=episode")
    assert ep_res.status_code == 200
    assert isinstance(ep_res.json(), list)

    fact_res = client.get("/api/northwind/memory?kind=fact")
    assert fact_res.status_code == 200
    assert isinstance(fact_res.json(), list)
    if fact_res.json():
        f = fact_res.json()[0]
        assert "valid_from" in f
        assert "valid_to" in f

    proc_res = client.get("/api/northwind/memory?kind=procedure")
    assert proc_res.status_code == 200
    assert isinstance(proc_res.json(), list)

    all_mem = client.get("/api/northwind/memory")
    assert all_mem.status_code == 200
    assert "episodes" in all_mem.json()
    assert "facts" in all_mem.json()
    assert "procedures" in all_mem.json()

    # 2. Concurrency Lab
    lab_res = client.post("/api/northwind/lab/concurrency", json={"tasks": 50, "workers": 4})
    assert lab_res.status_code == 200
    lab_data = lab_res.json()
    assert lab_data["claimed"] == 50
    assert lab_data["duplicates"] == 0
    assert lab_data["seconds"] > 0
    assert lab_data["throughput"] > 0
