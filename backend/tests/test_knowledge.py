import pytest
from app.tools.knowledge import (
    blast_radius,
    service_criticality,
    choke_points,
    dependency_path,
    find_experts,
    customer_history,
    trace_decision,
    get_doc,
    resolve_service,
)
from app.tools import call_tool


def test_blast_radius_ledger_dependents():
    res = blast_radius("northwind", "svc_ledger_db", direction="dependents", max_hops=4)
    services = {s["id"]: s for s in res.data["services"]}

    expected_ids = {
        "svc_payments_api",
        "svc_billing_worker",
        "svc_invoice_service",
        "svc_reporting_service",
        "svc_checkout_api",
        "svc_checkout_web",
        "svc_admin_console",
    }
    assert set(services.keys()) == expected_ids, f"Mismatch: {set(services.keys()) ^ expected_ids}"
    assert services["svc_checkout_web"]["hops"] == 3
    assert services["svc_admin_console"]["hops"] == 2


def test_blast_radius_payments_dependents():
    res = blast_radius("northwind", "svc_payments_api", direction="dependents", max_hops=4)
    services = {s["id"]: s for s in res.data["services"]}
    expected_ids = {"svc_checkout_api", "svc_checkout_web"}
    assert set(services.keys()) == expected_ids


def test_blast_radius_payments_dependencies():
    res = blast_radius("northwind", "svc_payments_api", direction="dependencies", max_hops=4)
    services = {s["id"]: s for s in res.data["services"]}
    expected_ids = {"svc_ledger_db", "svc_fraud_service", "svc_event_bus", "svc_feature_store"}
    assert set(services.keys()) == expected_ids


def test_service_criticality():
    res = service_criticality("northwind", top_k=5)
    crit_ids = [c["id"] for c in res.data["criticality"]]
    assert "svc_ledger_db" in crit_ids, f"svc_ledger_db not in top 5: {crit_ids}"


def test_dependency_path():
    res = dependency_path("northwind", "svc_checkout_web", "svc_ledger_db")
    expected_path = ["svc_checkout_web", "svc_checkout_api", "svc_payments_api", "svc_ledger_db"]
    assert res.data["path"] == expected_path


def test_find_experts():
    res = find_experts("northwind", "svc_ledger_db", k=3)
    ranked = res.data["ranked"]
    assert len(ranked) >= 2
    # Priya Nair ranked first
    assert ranked[0]["id"] == "per_priya_nair"
    # Priya Nair is in skipped (on_leave)
    skipped_ids = [s["id"] for s in res.data["skipped"]]
    assert "per_priya_nair" in skipped_ids
    # Recommended is Dev Okafor
    assert res.data["recommended"]["id"] == "per_dev_okafor"


def test_trace_decision():
    res = trace_decision("northwind", "svc_ledger_db")
    assert res.data["active"]["id"] == "dec_029"
    lineage_ids = [d["id"] for d in res.data["lineage"]]
    assert "dec_017" in lineage_ids


def test_customer_history():
    res = customer_history("northwind", "orbit", days=30)
    tickets = res.data["tickets"]
    assert len(tickets) >= 1
    orbit_tkt = next((t for t in tickets if t["ticket_id"] == "tkt_orbit_timeouts"), None)
    assert orbit_tkt is not None
    assert orbit_tkt["incident_id"] == "inc_2041"


def test_call_tool_wrapper():
    res = call_tool("northwind", "blast_radius", {"service_id": "svc_payments_api"})
    assert "Tool error" not in res.summary
    assert res.data["service_id"] == "svc_payments_api"
    assert len(res.cypher) > 0
