import pytest
from typing import Any, Dict, List, Tuple
from app.agents.events import get_bus
from app.agents.orchestrator import run_mission
from app.coordination.tasks import get_run_tasks
from app.db import graph_for
from app.seed.load import load_tenant


@pytest.fixture(scope="module", autouse=True)
def restore_seed():
    yield
    load_tenant("northwind", reset=True)


def test_orchestrator_respond_mode_offline():
    """Verifies respond mode end-to-end with injected agent and synthesizer (no network)."""

    def fake_agent(
        system_instruction: str,
        user_input: str,
        declarations: List[Dict[str, Any]],
        execute: Any,
        **kwargs,
    ) -> Tuple[str, int]:
        if "Scout" in system_instruction:
            # Call blast_radius
            execute("blast_radius", {"service_id": "svc_payments_api", "direction": "dependents"})
            return "Scout found [[svc_payments_api]] dependents [[svc_checkout_api]].", 1
        elif "Archivist" in system_instruction:
            # Call similar_incidents
            execute("similar_incidents", {"text": "latency", "service_ids": ["svc_payments_api"]})
            return "Archivist found [[inc_2041]].", 1
        elif "Responder" in system_instruction:
            # Propose action
            execute("page_person", {
                "person_id": "per_dev_okafor",
                "message": "Please inspect PgBouncer pool",
                "reason": "Expert for [[svc_ledger_db]]",
            })
            return "Proposed paging Dev Okafor.", 1
        return "Generic response", 0

    def fake_synthesizer(sys_inst: str, prompt: str) -> str:
        # Deliberately includes one valid ID (svc_payments_api) and one ungrounded ID (fake_invented_service)
        return (
            "### Summary\n"
            "High latency on [[svc_payments_api]].\n\n"
            "### Likely cause\n"
            "Connection saturation documented in [[inc_2041]].\n\n"
            "### Ungrounded Hallucination\n"
            "Invented node [[fake_invented_service]]."
        )

    run_id = run_mission(
        tenant="northwind",
        mode="respond",
        text="payments-api p99 latency spike",
        agent_runner=fake_agent,
        synthesizer_fn=fake_synthesizer,
    )

    # 1. Verify tasks
    task_data = get_run_tasks("northwind", run_id)
    tasks = task_data["tasks"]
    kinds = [t["kind"] for t in tasks]
    assert "investigate" in kinds
    assert "recall" in kinds
    assert "act" in kinds
    assert len(tasks) == 3

    # Every task claimed and done
    for t in tasks:
        assert t["status"] == "done"
        assert t["owner"] in ("scout", "archivist", "responder")

    # 2. Verify NEXT handoffs
    next_edges = task_data["next"]
    assert len(next_edges) == 2
    handoff_targets = [e["dst"] for e in next_edges]
    act_task_id = next(t["id"] for t in tasks if t["kind"] == "act")
    assert handoff_targets == [act_task_id, act_task_id]

    # 3. Verify event stream order
    bus = get_bus("northwind", run_id)
    event_types = [e["type"] for e in bus.events]
    assert event_types[0] == "run.started"
    assert "memory.recalled" in event_types
    assert "task.created" in event_types
    assert "task.claimed" in event_types
    assert "handoff" in event_types
    assert "action.proposed" in event_types
    assert "answer.final" in event_types
    assert event_types[-1] == "run.completed"

    # 4. Verify citation validation
    ans_event = next(e for e in bus.events if e["type"] == "answer.final")
    valid_cits = ans_event["data"]["citations"]
    ungrounded_cits = ans_event["data"]["ungrounded"]

    assert "svc_payments_api" in valid_cits
    assert "inc_2041" in valid_cits
    assert "fake_invented_service" in ungrounded_cits
    # Double brackets must be stripped for ungrounded citations in final text
    assert "[[fake_invented_service]]" not in ans_event["data"]["text"]
    assert "fake_invented_service" in ans_event["data"]["text"]

    # 5. Verify Action node created in graph
    g = graph_for("northwind")
    act_res = g.query("MATCH (r:Run {id: $rid})-[:PROPOSED]->(a:Action) RETURN a.kind, a.status", {"rid": run_id})
    assert len(act_res.result_set) == 1
    assert act_res.result_set[0][0] == "page_person"
    assert act_res.result_set[0][1] == "proposed"


def test_orchestrator_ask_mode_offline():
    """Verifies ask mode creates investigate + recall tasks, but NO act task and NO actions."""

    def fake_agent(system_instruction: str, *args, **kwargs) -> Tuple[str, int]:
        return "Observation.", 0

    def fake_synthesizer(*args, **kwargs) -> str:
        return "Answer."

    run_id = run_mission(
        tenant="northwind",
        mode="ask",
        text="What are the dependencies of auth-service?",
        agent_runner=fake_agent,
        synthesizer_fn=fake_synthesizer,
    )

    task_data = get_run_tasks("northwind", run_id)
    tasks = task_data["tasks"]
    kinds = [t["kind"] for t in tasks]
    assert kinds == ["investigate", "recall"]
    assert "act" not in kinds

    # No proposed actions in graph
    g = graph_for("northwind")
    act_res = g.query("MATCH (r:Run {id: $rid})-[:PROPOSED]->(a:Action) RETURN a", {"rid": run_id})
    assert len(act_res.result_set) == 0


def test_orchestrator_error_handling():
    """Verifies that failures during task execution mark the run failed cleanly."""

    def failing_agent(*args, **kwargs):
        raise ValueError("Simulated network timeout during tool loop")

    with pytest.raises(Exception, match="Investigation failed"):
        run_mission(
            tenant="northwind",
            mode="respond",
            text="Failing run test",
            agent_runner=failing_agent,
        )
