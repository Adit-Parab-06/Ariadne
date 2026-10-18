import contextvars
from typing import Any, Dict, List, Optional

from app.coordination.tasks import record_action
from app.db import graph_for
from app.tools import tool
from app.tools.evidence import Evidence, ToolResult

# ContextVar so actions know the active run_id in the execution thread
current_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_run_id", default="")


@tool(
    name="page_person",
    description="Proposes paging an on-call engineer or expert. Fails if the person's status is not 'available'.",
    params={
        "type": "object",
        "properties": {
            "person_id": {"type": "string", "description": "Person ID (e.g. per_dev_okafor)"},
            "message": {"type": "string", "description": "Urgent paging message"},
            "reason": {"type": "string", "description": "Justification citing evidence IDs"},
        },
        "required": ["person_id", "message", "reason"],
    },
    agents=["responder"],
    readonly=False,
)
def page_person(
    tenant: str,
    person_id: str,
    message: str,
    reason: str,
    run_id: Optional[str] = None,
) -> ToolResult:
    rid = run_id or current_run_id.get() or "run_unspecified"
    g = graph_for(tenant)
    evidence = Evidence()

    # Verify person and check availability
    res = g.ro_query("MATCH (p:Person {id: $pid}) RETURN p.name, p.status", {"pid": person_id})
    if not res.result_set:
        return ToolResult(
            summary=f"Tool error: Person '{person_id}' not found in graph",
            data={"error": f"Person '{person_id}' not found"},
            evidence=evidence,
            cypher=["MATCH (p:Person {id: $pid}) RETURN p.name, p.status"],
        )

    pname, pstatus = res.result_set[0]
    if pstatus != "available":
        return ToolResult(
            summary=f"Tool error: Cannot page {pname} ({person_id}): status is '{pstatus}', only 'available' engineers can be paged",
            data={"error": f"Person status is '{pstatus}'"},
            evidence=evidence,
            cypher=["MATCH (p:Person {id: $pid}) RETURN p.name, p.status"],
        )

    payload = {
        "person_id": person_id,
        "person_name": pname,
        "message": message,
        "reason": reason,
    }
    action_id = record_action(tenant, rid, "page_person", payload)

    evidence.add_node(person_id, "Person", pname)
    evidence.add_node(action_id, "Action", f"Page {pname}")
    evidence.add_edge(action_id, "TARGETS", person_id)

    summary = f"Proposed action: Page {pname} ({person_id}) - '{message}'"
    return ToolResult(
        summary=summary,
        data={"action_id": action_id, "payload": payload},
        evidence=evidence,
        cypher=["MATCH (r:Run) CREATE (a:Action) ..."],
    )


@tool(
    name="create_ticket",
    description="Proposes filing an incident or remediation ticket for an affected service.",
    params={
        "type": "object",
        "properties": {
            "service_id": {"type": "string", "description": "Affected Service ID"},
            "title": {"type": "string", "description": "Ticket summary title"},
            "body": {"type": "string", "description": "Detailed remediation instructions"},
            "reason": {"type": "string", "description": "Reasoning citing evidence node IDs"},
        },
        "required": ["service_id", "title", "body", "reason"],
    },
    agents=["responder"],
    readonly=False,
)
def create_ticket(
    tenant: str,
    service_id: str,
    title: str,
    body: str,
    reason: str,
    run_id: Optional[str] = None,
) -> ToolResult:
    rid = run_id or current_run_id.get() or "run_unspecified"
    g = graph_for(tenant)
    evidence = Evidence()

    s_res = g.ro_query("MATCH (s:Service {id: $sid}) RETURN s.name", {"sid": service_id})
    sname = s_res.result_set[0][0] if s_res.result_set else service_id

    payload = {
        "service_id": service_id,
        "service_name": sname,
        "title": title,
        "body": body,
        "reason": reason,
    }
    action_id = record_action(tenant, rid, "create_ticket", payload)

    evidence.add_node(service_id, "Service", sname)
    evidence.add_node(action_id, "Action", f"Ticket: {title}")
    evidence.add_edge(action_id, "TARGETS", service_id)

    summary = f"Proposed action: Create ticket for {sname} - '{title}'"
    return ToolResult(
        summary=summary,
        data={"action_id": action_id, "payload": payload},
        evidence=evidence,
        cypher=["MATCH (r:Run) CREATE (a:Action) ..."],
    )


@tool(
    name="post_status_update",
    description="Proposes broadcasting a status update to internal or external stakeholders.",
    params={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Status update text"},
            "audience": {"type": "string", "description": "Audience: 'internal', 'customers', or 'executive'"},
            "reason": {"type": "string", "description": "Justification citing evidence IDs"},
        },
        "required": ["text", "audience", "reason"],
    },
    agents=["responder"],
    readonly=False,
)
def post_status_update(
    tenant: str,
    text: str,
    audience: str,
    reason: str,
    run_id: Optional[str] = None,
) -> ToolResult:
    rid = run_id or current_run_id.get() or "run_unspecified"
    evidence = Evidence()

    payload = {
        "text": text,
        "audience": audience,
        "reason": reason,
    }
    action_id = record_action(tenant, rid, "post_status_update", payload)

    evidence.add_node(action_id, "Action", f"Status Update ({audience})")

    summary = f"Proposed action: Post status update to {audience} - '{text[:60]}...'"
    return ToolResult(
        summary=summary,
        data={"action_id": action_id, "payload": payload},
        evidence=evidence,
        cypher=["MATCH (r:Run) CREATE (a:Action) ..."],
    )
