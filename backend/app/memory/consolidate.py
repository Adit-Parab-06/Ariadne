import json
import logging
import re
from typing import Any, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from app.db import graph_for
from app.llm import generate_text
from app.memory.store import bump_procedure, create_procedure, upsert_fact, write_episode

logger = logging.getLogger(__name__)


class FactUpdate(BaseModel):
    service_id: str
    predicate: str
    text: str


class ProcedureUpdate(BaseModel):
    reuse_id: Optional[str] = None
    name: str
    trigger_text: str
    steps: List[str] = Field(default_factory=list, max_length=6)


class ConsolidationPayload(BaseModel):
    episode_summary: str
    outcome: Literal["success", "partial", "failure"]
    fact_updates: List[FactUpdate] = Field(default_factory=list, max_length=3)
    procedure: Optional[ProcedureUpdate] = None


def _clean_json_text(text: str) -> str:
    """Strips Markdown markdown code fences (```json ... ```) from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def _validate_service_ids(tenant: str, payload: ConsolidationPayload) -> None:
    g = graph_for(tenant)
    for fact in payload.fact_updates:
        res = g.ro_query("MATCH (s:Service {id: $sid}) RETURN count(s)", {"sid": fact.service_id})
        if not res.result_set or res.result_set[0][0] == 0:
            raise ValueError(f"Service '{fact.service_id}' does not exist in graph for tenant '{tenant}'")


SYSTEM_PROMPT = """You are a post-incident memory consolidation engine.
Synthesize the incident resolution note and run summary into structured institutional memory.
You must output ONLY raw JSON without commentary or code fences matching this exact schema:
{
  "episode_summary": "1-2 sentence executive summary of how the incident was resolved",
  "outcome": "success" | "partial" | "failure",
  "fact_updates": [
    {
      "service_id": "svc_...",
      "predicate": "property_or_config_name",
      "text": "Human readable statement of the new factual state"
    }
  ],
  "procedure": {
    "reuse_id": "prc_..." or null,
    "name": "Standard Operating Procedure name",
    "trigger_text": "Symptoms that trigger this procedure",
    "steps": ["Step 1", "Step 2", "Step 3"]
  } or null
}
Constraints:
- At most 3 fact_updates.
- At most 6 procedure steps.
- service_id MUST reference an existing service from the graph.
"""


def consolidate(
    tenant: str,
    run_id: str,
    resolution_note: str,
    run_summary: str,
    llm_fn: Optional[Callable[[str, str], str]] = None,
) -> List[Dict[str, str]]:
    """
    Consolidates incident resolution into Episode, Fact, and Procedure nodes.
    Accepts an injectable LLM function for deterministic, offline testing.
    Returns written nodes list [{id, label, name}] for the UI.
    """
    call_llm = llm_fn if llm_fn is not None else lambda sys_inst, prompt: generate_text(sys_inst, prompt, thinking_level="low")

    prompt = (
        f"Tenant: {tenant}\n"
        f"Run ID: {run_id}\n"
        f"Resolution Note: {resolution_note}\n"
        f"Run Summary: {run_summary}\n"
        "Extract the updated facts, procedure, and episode outcome."
    )

    payload: Optional[ConsolidationPayload] = None
    last_error: Optional[str] = None

    for attempt in range(2):
        if attempt > 0:
            prompt_with_err = (
                f"{prompt}\n\n"
                f"Your previous attempt produced an invalid response: {last_error}\n"
                "Please fix this and return strictly valid JSON matching the schema."
            )
            raw_response = call_llm(SYSTEM_PROMPT, prompt_with_err)
        else:
            raw_response = call_llm(SYSTEM_PROMPT, prompt)

        try:
            cleaned = _clean_json_text(raw_response)
            parsed = json.loads(cleaned)
            validated = ConsolidationPayload.model_validate(parsed)
            _validate_service_ids(tenant, validated)
            payload = validated
            break
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Consolidation parse/validation failure (attempt {attempt + 1}/2): {e}")

    if payload is None:
        # Fallback to minimal episode if LLM fails repeatedly
        payload = ConsolidationPayload(
            episode_summary=resolution_note[:200],
            outcome="success",
            fact_updates=[],
            procedure=None,
        )

    written_nodes: List[Dict[str, str]] = []

    # 1. Update/Create Procedure
    procedure_id: Optional[str] = None
    if payload.procedure:
        proc = payload.procedure
        if proc.reuse_id:
            bump_procedure(tenant, proc.reuse_id, success=(payload.outcome == "success"))
            procedure_id = proc.reuse_id
            written_nodes.append({"id": procedure_id, "label": "Procedure", "name": proc.name})
        else:
            # Service IDs for procedure
            service_ids = [f.service_id for f in payload.fact_updates]
            procedure_id = create_procedure(
                tenant,
                name=proc.name,
                trigger_text=proc.trigger_text,
                steps=proc.steps,
                service_ids=service_ids,
            )
            written_nodes.append({"id": procedure_id, "label": "Procedure", "name": proc.name})

    # 2. Write Episode
    involved_services = list(set(f.service_id for f in payload.fact_updates))
    epi_id = write_episode(
        tenant=tenant,
        run_id=run_id,
        goal=resolution_note,
        outcome=payload.outcome,
        summary=payload.episode_summary,
        service_ids=involved_services,
        incident_ids=[],
        procedure_id=procedure_id,
        fact_ids=(),
    )
    written_nodes.append({"id": epi_id, "label": "Episode", "name": payload.episode_summary[:40]})

    # 3. Upsert Facts
    for fact in payload.fact_updates:
        new_fid, old_fid = upsert_fact(
            tenant=tenant,
            subject_id=fact.service_id,
            predicate=fact.predicate,
            text=fact.text,
            confidence=0.98,
            source_episode_id=epi_id,
        )
        written_nodes.append({"id": new_fid, "label": "Fact", "name": fact.text})

    return written_nodes
