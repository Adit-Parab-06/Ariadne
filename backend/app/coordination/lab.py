import threading
import time
import uuid
from typing import Any, Dict, List

from app.coordination.tasks import (
    claim_task,
    complete_task,
    create_run,
    end_run,
    now_ms,
)
from app.db import graph_for
from app.tools.knowledge import blast_radius


def run_concurrency_lab(
    tenant: str,
    tasks: int = 200,
    workers: int = 8,
) -> Dict[str, Any]:
    """
    Executes the Concurrency Lab benchmark:
    - Creates N open tasks under a new Run.
    - Spawns W parallel worker threads contending for tasks via atomic conditional Cypher claims.
    - Concurrently runs 2 background reader threads executing blast_radius on svc_ledger_db.
    - Measures actual elapsed time, throughput, and verifies zero duplicate claims.
    """
    g = graph_for(tenant)
    run_id = create_run(tenant, mode="lab", mission=f"Concurrency benchmark: {tasks} tasks, {workers} workers")
    now = now_ms()

    # 1. Batch create N tasks
    task_ids = [f"tsk_lab_{uuid.uuid4().hex[:8]}" for _ in range(tasks)]
    batch_size = 100
    for i in range(0, len(task_ids), batch_size):
        chunk = task_ids[i : i + batch_size]
        g.query(
            "MATCH (r:Run {id: $rid}) "
            "UNWIND $batch AS tid "
            "CREATE (t:Task { "
            "  id: tid, run_id: $rid, kind: 'lab', status: 'open', owner: '', "
            "  payload: '{}', result: '', created_at: $now, claimed_at: 0, done_at: 0 "
            "}) "
            "CREATE (r)-[:HAS_TASK]->(t)",
            {"rid": run_id, "batch": chunk, "now": now},
        )

    claimed_lock = threading.Lock()
    all_claimed_tasks: List[str] = []
    stop_readers_event = threading.Event()
    read_counts = [0, 0]

    def reader_worker(reader_idx: int):
        reads = 0
        while not stop_readers_event.is_set():
            try:
                blast_radius(tenant, "svc_ledger_db", direction="dependents", max_hops=3)
                reads += 1
            except Exception:
                pass
            time.sleep(0.005)
        read_counts[reader_idx] = reads

    def task_worker(worker_idx: int):
        agent_id = f"worker_{worker_idx}"
        worker_claims = []

        while True:
            # Read up to 5 open tasks
            res = g.ro_query(
                "MATCH (r:Run {id: $rid})-[:HAS_TASK]->(t:Task {status: 'open'}) "
                "RETURN t.id LIMIT 5",
                {"rid": run_id},
            )
            open_ids = [row[0] for row in (res.result_set or [])]
            if not open_ids:
                # Double check to prevent early exit
                check_res = g.ro_query(
                    "MATCH (r:Run {id: $rid})-[:HAS_TASK]->(t:Task {status: 'open'}) "
                    "RETURN count(t)",
                    {"rid": run_id},
                )
                if not check_res.result_set or check_res.result_set[0][0] == 0:
                    break
                time.sleep(0.01)
                continue

            for tid in open_ids:
                if claim_task(tenant, tid, agent_id):
                    worker_claims.append(tid)
                    complete_task(tenant, tid, {"worker": agent_id}, owner=agent_id)

        with claimed_lock:
            all_claimed_tasks.extend(worker_claims)

    start_time = time.perf_counter()

    # Start reader threads
    reader_threads = [
        threading.Thread(target=reader_worker, args=(0,)),
        threading.Thread(target=reader_worker, args=(1,)),
    ]
    for rt in reader_threads:
        rt.start()

    # Start worker threads
    worker_threads = [
        threading.Thread(target=task_worker, args=(w,))
        for w in range(workers)
    ]
    for wt in worker_threads:
        wt.start()

    # Wait for workers
    for wt in worker_threads:
        wt.join()

    # Stop readers
    stop_readers_event.set()
    for rt in reader_threads:
        rt.join()

    duration_sec = time.perf_counter() - start_time
    duration_ms = int(duration_sec * 1000)

    # Compute duplicates
    total_claims = len(all_claimed_tasks)
    unique_claims = len(set(all_claimed_tasks))
    duplicates = total_claims - unique_claims

    # Verify graph state
    verify_res = g.ro_query(
        "MATCH (r:Run {id: $rid})-[:HAS_TASK]->(t:Task) "
        "RETURN count(t), count(CASE WHEN t.status = 'done' THEN 1 END)",
        {"rid": run_id},
    )
    total_in_graph, done_in_graph = verify_res.result_set[0]

    end_run(
        tenant,
        run_id=run_id,
        status="completed",
        tool_calls=total_claims,
        duration_ms=duration_ms,
    )

    throughput = round(total_claims / duration_sec, 1) if duration_sec > 0 else 0.0

    return {
        "run_id": run_id,
        "claimed": total_claims,
        "unique_claimed": unique_claims,
        "duplicates": duplicates,
        "total_in_graph": total_in_graph,
        "done_in_graph": done_in_graph,
        "seconds": round(duration_sec, 3),
        "throughput": throughput,
        "concurrent_reads": sum(read_counts),
    }
