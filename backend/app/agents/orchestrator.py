import argparse
import json
import logging
import re
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents.events import EventBus, get_bus
from app.agents.prompts import (
    ARCHIVIST_PROMPT,
    RESPONDER_PROMPT,
    SCOUT_PROMPT,
    SYNTHESIZER_PROMPT,
)
from app.coordination.tasks import (
    claim_task,
    complete_task,
    create_run,
    create_task,
    end_run,
    fail_task,
    link_next,
)
from app.db import graph_for
from app.llm import generate_text, run_agent
from app.memory.store import (
    add_message,
    recall,
    start_conversation,
)
from app.tools import call_tool, gemini_declarations
from app.tools.actions import current_run_id
from app.tools.evidence import Evidence, ToolResult, llm_view

logger = logging.getLogger(__name__)


def validate_citations(
    raw_text: str, allowed_ids: Set[str]
) -> Tuple[str, List[str], List[str]]:
    """
    Finds all [[node_id]] citations in raw_text.
    Valid citations (present in allowed_ids) are preserved.
    Ungrounded citations are stripped of double brackets and flagged.
    Returns (cleaned_text, valid_ids, ungrounded_ids).
    """
    pattern = re.compile(r"\[\[([a-zA-Z0-9_\-]+)\]\]")
    valid_ids: List[str] = []
    ungrounded_ids: List[str] = []

    def replace_citation(match):
        node_id = match.group(1)
        if node_id in allowed_ids:
            if node_id not in valid_ids:
                valid_ids.append(node_id)
            return f"[[{node_id}]]"
        else:
            if node_id not in ungrounded_ids:
                ungrounded_ids.append(node_id)
            return node_id  # Strip brackets for ungrounded citations

    cleaned_text = pattern.sub(replace_citation, raw_text)
    return cleaned_text, valid_ids, ungrounded_ids


def run_mission(
    tenant: str,
    mode: str,
    text: str,
    conversation_id: Optional[str] = None,
    bus: Optional[EventBus] = None,
    agent_runner: Optional[Callable] = None,
    synthesizer_fn: Optional[Callable] = None,
    run_id: Optional[str] = None,
) -> str:
    """
    Orchestrates the Ariadne multi-agent mission workflow:
    1. Sets up persistent conversation & Run node.
    2. Zero-LLM graph memory prefetch (recall_memory).
    3. Spawns Scout and Archivist in parallel threads coordinated via Task nodes.
    4. Records handoffs ([:NEXT]) and runs Responder (if mode == 'respond').
    5. Synthesizes final response and validates [[node_id]] citations against evidence.
    6. Persists Answer node and CITES edges in FalkorDB.
    """
    start_time = time.perf_counter()

    # 1. Setup conversation & Run
    conv_id = conversation_id or start_conversation(tenant)
    add_message(tenant, conv_id, role="user", text=text)

    run_id = run_id or create_run(tenant, mode=mode, mission=text, conversation_id=conv_id)
    event_bus = bus or get_bus(tenant, run_id)
    token = current_run_id.set(run_id)

    event_bus.publish(
        "run.started",
        agent="orchestrator",
        data={
            "run_id": run_id,
            "tenant": tenant,
            "mode": mode,
            "mission": text,
            "conversation_id": conv_id,
        },
    )

    try:
        # 2. Zero-LLM Memory Prefetch
        event_bus.publish("agent.status", agent="orchestrator", data={"status": "Prefetching graph memory..."})
        prefetch_recalled = recall(tenant, text=text, service_ids=[], k=3)
        memories_count = (
            len(prefetch_recalled["episodes"])
            + len(prefetch_recalled["facts"])
            + len(prefetch_recalled["procedures"])
        )
        event_bus.publish(
            "memory.recalled",
            agent="orchestrator",
            data={
                "items": {
                    "episodes": [e["id"] for e in prefetch_recalled["episodes"]],
                    "facts": [f["id"] for f in prefetch_recalled["facts"]],
                    "procedures": [p["id"] for p in prefetch_recalled["procedures"]],
                },
                "count": memories_count,
            },
        )

        hints = ""
        if prefetch_recalled["episodes"]:
            hints = "Memory hints (verify before trusting): " + "; ".join(
                f"[{e['id']}] {e['summary']}" for e in prefetch_recalled["episodes"]
            )

        # 3. Create parallel tasks
        inv_tid = create_task(tenant, run_id, "investigate", {"text": text, "hints": hints})
        rec_tid = create_task(tenant, run_id, "recall", {"text": text})

        event_bus.publish("task.created", agent="orchestrator", data={"task_id": inv_tid, "kind": "investigate"})
        event_bus.publish("task.created", agent="orchestrator", data={"task_id": rec_tid, "kind": "recall"})

        # Shared evidence collector across threads
        evidence_lock = threading.Lock()
        collected_evidence = Evidence()
        total_tool_calls_counter = 0

        # Injectable agent runner (for tests) or production run_agent
        execute_agent_loop = agent_runner if agent_runner is not None else run_agent

        def make_executor(agent_name: str):
            def execute(name: str, args: Dict[str, Any]) -> Tuple[Dict[str, Any], ToolResult]:
                res = call_tool(tenant, name, args)
                with evidence_lock:
                    collected_evidence.merge(res.evidence)
                payload = llm_view(res)
                if "action_id" in res.data:
                    act_payload = res.data.get("payload", {})
                    act_obj = {
                        "id": res.data["action_id"],
                        "kind": name,
                        "payload": act_payload,
                        "status": "proposed",
                    }
                    proposed_actions.append(act_obj)
                    event_bus.publish("action.proposed", agent=agent_name, data={"action": act_obj})
                return payload, res

            return execute

        scout_findings = ""
        archivist_findings = ""
        scout_error = None
        archivist_error = None

        def run_scout():
            nonlocal scout_findings, scout_error, total_tool_calls_counter
            claim_task(tenant, inv_tid, "scout")
            event_bus.publish("task.claimed", agent="scout", data={"task_id": inv_tid})
            event_bus.publish("agent.status", agent="scout", data={"status": "Scout investigating topology and blast radius..."})

            scout_input = f"Alert: {text}\n{hints}\nInvestigate impacted services, dependencies, and criticality."
            scout_decls = gemini_declarations("scout")

            def on_scout_event(etype: str, edata: Dict[str, Any]):
                if etype == "tool.call":
                    event_bus.publish("tool.call", agent="scout", data=edata)
                elif etype == "tool.result":
                    tr: ToolResult = edata["result"]
                    event_bus.publish(
                        "tool.result",
                        agent="scout",
                        data={
                            "tool": edata["tool"],
                            "summary": tr.summary,
                            "evidence": tr.evidence.to_json(),
                            "cypher": tr.cypher,
                            "ms": tr.ms,
                        },
                    )

            try:
                findings, calls = execute_agent_loop(
                    system_instruction=SCOUT_PROMPT,
                    user_input=scout_input,
                    declarations=scout_decls,
                    execute=make_executor("scout"),
                    thinking_level="low",
                    max_rounds=6,
                    on_event=on_scout_event,
                )
                scout_findings = findings
                with evidence_lock:
                    total_tool_calls_counter += calls
                complete_task(tenant, inv_tid, {"findings": findings}, owner="scout")
                event_bus.publish("task.done", agent="scout", data={"task_id": inv_tid, "findings": findings})
            except Exception as e:
                scout_error = str(e)
                fail_task(tenant, inv_tid, str(e), owner="scout")

        def run_archivist():
            nonlocal archivist_findings, archivist_error, total_tool_calls_counter
            claim_task(tenant, rec_tid, "archivist")
            event_bus.publish("task.claimed", agent="archivist", data={"task_id": rec_tid})
            event_bus.publish("agent.status", agent="archivist", data={"status": "Archivist searching past incidents and runbooks..."})

            arch_input = f"Alert: {text}\nRecall past incidents, runbooks, available experts, and ADR decisions."
            arch_decls = gemini_declarations("archivist")

            def on_arch_event(etype: str, edata: Dict[str, Any]):
                if etype == "tool.call":
                    event_bus.publish("tool.call", agent="archivist", data=edata)
                elif etype == "tool.result":
                    tr: ToolResult = edata["result"]
                    event_bus.publish(
                        "tool.result",
                        agent="archivist",
                        data={
                            "tool": edata["tool"],
                            "summary": tr.summary,
                            "evidence": tr.evidence.to_json(),
                            "cypher": tr.cypher,
                            "ms": tr.ms,
                        },
                    )

            try:
                findings, calls = execute_agent_loop(
                    system_instruction=ARCHIVIST_PROMPT,
                    user_input=arch_input,
                    declarations=arch_decls,
                    execute=make_executor("archivist"),
                    thinking_level="low",
                    max_rounds=6,
                    on_event=on_arch_event,
                )
                archivist_findings = findings
                with evidence_lock:
                    total_tool_calls_counter += calls
                complete_task(tenant, rec_tid, {"findings": findings}, owner="archivist")
                event_bus.publish("task.done", agent="archivist", data={"task_id": rec_tid, "findings": findings})
            except Exception as e:
                archivist_error = str(e)
                fail_task(tenant, rec_tid, str(e), owner="archivist")

        t_scout = threading.Thread(target=run_scout)
        t_arch = threading.Thread(target=run_archivist)

        t_scout.start()
        t_arch.start()

        t_scout.join(timeout=180.0)
        t_arch.join(timeout=180.0)

        if t_scout.is_alive() or t_arch.is_alive():
            raise TimeoutError("Investigation phase timed out after 180 seconds")

        if scout_error or archivist_error:
            raise RuntimeError(f"Investigation failed: Scout error={scout_error}, Archivist error={archivist_error}")

        # 4. Handoff & Responder (if respond mode)
        proposed_actions = []
        if mode == "respond":
            act_tid = create_task(
                tenant,
                run_id,
                "act",
                {"scout": scout_findings, "archivist": archivist_findings},
            )
            event_bus.publish("task.created", agent="orchestrator", data={"task_id": act_tid, "kind": "act"})

            link_next(tenant, inv_tid, act_tid, note="Investigative findings handed off to Responder")
            link_next(tenant, rec_tid, act_tid, note="Historical knowledge handed off to Responder")

            event_bus.publish(
                "handoff",
                agent="orchestrator",
                data={
                    "from": "scout & archivist",
                    "to": "responder",
                    "note": "Handoff to formulate remediation actions",
                },
            )

            claim_task(tenant, act_tid, "responder")
            event_bus.publish("task.claimed", agent="responder", data={"task_id": act_tid})
            event_bus.publish("agent.status", agent="responder", data={"status": "Responder formulating action proposals..."})

            responder_decls = gemini_declarations("responder")
            responder_input = (
                f"Mission: {text}\n"
                f"Scout findings:\n{scout_findings}\n\n"
                f"Archivist findings:\n{archivist_findings}\n\n"
                "Propose up to three actions with action tools (page available engineer, file ticket, post status update)."
            )

            def on_responder_event(etype: str, edata: Dict[str, Any]):
                if etype == "tool.call":
                    event_bus.publish("tool.call", agent="responder", data=edata)
                elif etype == "tool.result":
                    tr: ToolResult = edata["result"]
                    event_bus.publish(
                        "tool.result",
                        agent="responder",
                        data={
                            "tool": edata["tool"],
                            "summary": tr.summary,
                            "evidence": tr.evidence.to_json(),
                            "cypher": tr.cypher,
                            "ms": tr.ms,
                        },
                    )

            r_findings, r_calls = execute_agent_loop(
                system_instruction=RESPONDER_PROMPT,
                user_input=responder_input,
                declarations=responder_decls,
                execute=make_executor("responder"),
                thinking_level="low",
                max_rounds=4,
                on_event=on_responder_event,
            )
            with evidence_lock:
                total_tool_calls_counter += r_calls
            complete_task(tenant, act_tid, {"actions": proposed_actions, "summary": r_findings}, owner="responder")
            event_bus.publish("task.done", agent="responder", data={"task_id": act_tid, "actions": proposed_actions})

        # 5. Synthesize final answer & validate citations
        event_bus.publish("agent.status", agent="synthesizer", data={"status": "Synthesizing grounded response..."})

        allowed_ids = set(collected_evidence.nodes.keys())
        allowed_list_str = ", ".join(sorted(allowed_ids))

        syn_prompt = (
            f"Mission: {text}\n\n"
            f"Scout findings:\n{scout_findings}\n\n"
            f"Archivist findings:\n{archivist_findings}\n\n"
            f"ALLOWED_IDS list (you MUST ONLY cite IDs from this list):\n{allowed_list_str}\n\n"
            "Format your answer under the headings: Summary, Likely cause, Impact, What to do, What we remember."
        )

        call_synthesizer = synthesizer_fn if synthesizer_fn is not None else generate_text
        raw_answer = call_synthesizer(SYNTHESIZER_PROMPT, syn_prompt)

        # Validate citations
        clean_text, valid_citations, ungrounded_citations = validate_citations(raw_answer, allowed_ids)

        # Store Answer node and CITES edges in graph
        g = graph_for(tenant)
        ans_id = f"ans_{uuid.uuid4().hex[:8]}"
        ans_ts = int(time.time() * 1000)

        g.query(
            "MATCH (r:Run {id: $rid}) "
            "CREATE (a:Answer {id: $aid, run_id: $rid, text: $text, ts: $ts}) "
            "CREATE (r)-[:ANSWERED]->(a)",
            {"rid": run_id, "aid": ans_id, "text": clean_text, "ts": ans_ts},
        )

        if valid_citations:
            g.query(
                "MATCH (a:Answer {id: $aid}) "
                "UNWIND $cids AS cid "
                "MATCH (n {id: cid}) "
                "MERGE (a)-[:CITES]->(n)",
                {"aid": ans_id, "cids": valid_citations},
            )

        add_message(tenant, conv_id, role="assistant", text=clean_text)

        event_bus.publish(
            "answer.final",
            agent="synthesizer",
            data={
                "answer_id": ans_id,
                "text": clean_text,
                "citations": valid_citations,
                "ungrounded": ungrounded_citations,
                "ungrounded_count": len(ungrounded_citations),
            },
        )

        # 6. Complete run
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        metrics = {
            "tool_calls": total_tool_calls_counter,
            "duration_ms": duration_ms,
            "memories_recalled": memories_count,
            "ungrounded_count": len(ungrounded_citations),
            "valid_citations_count": len(valid_citations),
            "evidence_nodes_count": len(collected_evidence.nodes),
        }

        end_run(
            tenant,
            run_id=run_id,
            status="completed",
            tool_calls=total_tool_calls_counter,
            duration_ms=duration_ms,
        )

        event_bus.publish("run.completed", agent="orchestrator", data={"metrics": metrics})
        return run_id

    except Exception as e:
        logger.exception(f"Run {run_id} failed: {e}")
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        end_run(tenant, run_id=run_id, status="failed", tool_calls=0, duration_ms=duration_ms)
        event_bus.publish("run.failed", agent="orchestrator", data={"error": str(e)})
        raise e
    finally:
        current_run_id.reset(token)


def main():
    parser = argparse.ArgumentParser(description="Run an Ariadne mission CLI")
    parser.add_argument("--tenant", choices=["northwind", "acme"], default="northwind")
    parser.add_argument("--mode", choices=["ask", "respond"], default="respond")
    parser.add_argument("--text", type=str, required=True, help="Alert description")
    args = parser.parse_args()

    print(f"\n=== ARIADNE MISSION ORCHESTRATOR ===")
    print(f"Tenant: {args.tenant} | Mode: {args.mode}")
    print(f"Mission: {args.text}\n")

    # Custom printer bus
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    bus = get_bus(args.tenant, run_id)

    # Monitor in background
    def print_events():
        for event in bus.subscribe(from_seq=0):
            etype = event["type"]
            agent = event["agent"]
            data = event["data"]
            if etype == "agent.status":
                print(f"  [{agent}] STATUS -> {data.get('status')}")
            elif etype == "memory.recalled":
                print(f"  [{agent}] RECALLED -> {data.get('count')} memory item(s)")
            elif etype == "tool.call":
                print(f"  [{agent}] TOOL CALL -> {data.get('tool')}({data.get('args')})")
            elif etype == "tool.result":
                print(f"  [{agent}] TOOL RESULT -> {data.get('summary')}")
            elif etype == "handoff":
                print(f"  [HANDOFF] {data.get('from')} -> {data.get('to')}: {data.get('note')}")
            elif etype == "action.proposed":
                act = data.get("action", {})
                print(f"  [ACTION PROPOSED] {act.get('kind')} (ID: {act.get('id')}): {act.get('payload')}")
            elif etype == "answer.final":
                print(f"\n=== FINAL ANSWER ===\n{data.get('text')}\n")
                print(f"Citations: {data.get('citations')}")
                print(f"Ungrounded Citations: {data.get('ungrounded')}")
            elif etype == "run.completed":
                print(f"\n[RUN COMPLETED] Metrics: {data.get('metrics')}\n")
            elif etype == "run.failed":
                print(f"\n[RUN FAILED] Error: {data.get('error')}\n")
            elif etype == "heartbeat":
                print("  ... [working] ...")

    t_print = threading.Thread(target=print_events)
    t_print.daemon = True
    t_print.start()

    run_mission(
        tenant=args.tenant,
        mode=args.mode,
        text=args.text,
        bus=bus,
    )
    t_print.join(timeout=1.0)


if __name__ == "__main__":
    main()
