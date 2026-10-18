import threading
import pytest
from app.coordination.lab import run_concurrency_lab
from app.coordination.tasks import (
    claim_task,
    complete_task,
    create_run,
    create_task,
    decide_action,
    get_run_tasks,
    link_next,
    record_action,
)
from app.db import graph_for


def test_50_threads_claim_same_task():
    """50 threads concurrently attempt to claim the exact same open task: exactly one must win."""
    run_id = create_run("northwind", mode="test", mission="Atomic claim stress test")
    task_id = create_task("northwind", run_id, "investigate", {"test": True})

    results = []
    lock = threading.Lock()
    barrier = threading.Barrier(50)

    def worker(worker_id: int):
        barrier.wait()  # synchronize all 50 threads to fire simultaneously
        win = claim_task("northwind", task_id, f"worker_{worker_id}")
        with lock:
            results.append((worker_id, win))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    winners = [wid for wid, win in results if win]
    assert len(winners) == 1, f"Atomic claim race failed! Winners count: {len(winners)} (expected exactly 1)"

    # Verify state in graph
    g = graph_for("northwind")
    res = g.query("MATCH (t:Task {id: $tid}) RETURN t.status, t.owner", {"tid": task_id})
    status, owner = res.result_set[0]
    assert status == "claimed"
    assert owner == f"worker_{winners[0]}"


def test_complete_task_by_non_owner():
    """A worker cannot complete a task claimed by someone else."""
    run_id = create_run("northwind", mode="test", mission="Owner check test")
    task_id = create_task("northwind", run_id, "investigate", {})

    # Agent 1 claims task
    claimed = claim_task("northwind", task_id, "agent_alice")
    assert claimed is True

    # Agent 2 tries to complete task
    success = complete_task("northwind", task_id, {"done": True}, owner="agent_bob")
    assert success is False, "Non-owner should not be able to complete task"

    # Task status in graph must still be claimed by alice
    g = graph_for("northwind")
    res = g.query("MATCH (t:Task {id: $tid}) RETURN t.status, t.owner", {"tid": task_id})
    status, owner = res.result_set[0]
    assert status == "claimed"
    assert owner == "agent_alice"


def test_decide_action_state_machine():
    """An action that is rejected cannot subsequently be approved."""
    run_id = create_run("northwind", mode="test", mission="Action state machine test")
    action_id = record_action(
        "northwind",
        run_id,
        "page_person",
        {"person_id": "per_dev_okafor", "message": "Paging engineer"},
    )

    # Reject action
    res = decide_action("northwind", action_id, "rejected")
    assert res["status"] == "rejected"

    # Attempt to approve already rejected action
    with pytest.raises(ValueError, match="not in 'proposed' state"):
        decide_action("northwind", action_id, "approved")


def test_concurrency_lab_200_tasks():
    """Runs the 200-task, 8-worker Concurrency Lab with zero duplicates."""
    metrics = run_concurrency_lab("northwind", tasks=200, workers=8)

    assert metrics["claimed"] == 200, f"Expected 200 claimed, got {metrics['claimed']}"
    assert metrics["duplicates"] == 0, f"Expected 0 duplicates, got {metrics['duplicates']}"
    assert metrics["done_in_graph"] == 200, f"Expected 200 done in graph, got {metrics['done_in_graph']}"
    assert metrics["seconds"] > 0
    assert metrics["throughput"] > 0
    assert metrics["concurrent_reads"] > 0
