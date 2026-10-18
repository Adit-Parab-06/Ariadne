import pytest
from app.db import graph_for


def test_northwind_seed():
    g = graph_for("northwind")

    # 1. At least 20 services
    res_svc = g.ro_query("MATCH (s:Service) RETURN count(s)")
    total_services = res_svc.result_set[0][0]
    assert total_services >= 20, f"Expected at least 20 services, got {total_services}"

    # 2. Transitive dependents of svc_ledger_db (who depends on svc_ledger_db)
    # DEPENDS_ON points from dependent -> dependency, so: (s)-[:DEPENDS_ON*1..6]->(ledger)
    res_dependents = g.ro_query(
        "MATCH (s:Service)-[:DEPENDS_ON*1..6]->(target:Service {id: 'svc_ledger_db'}) "
        "RETURN collect(DISTINCT s.id)"
    )
    dependents = set(res_dependents.result_set[0][0])
    expected_dependents = {
        "svc_payments_api",
        "svc_billing_worker",
        "svc_invoice_service",
        "svc_reporting_service",
        "svc_checkout_api",
        "svc_checkout_web",
        "svc_admin_console",
    }
    assert dependents == expected_dependents, (
        f"Transitive dependents mismatch.\nGot: {dependents}\nExpected: {expected_dependents}\n"
        f"Diff: {dependents ^ expected_dependents}"
    )

    # 3. Transitive dependencies of svc_payments_api (what svc_payments_api depends on)
    # (payments)-[:DEPENDS_ON*1..6]->(s)
    res_dependencies = g.ro_query(
        "MATCH (source:Service {id: 'svc_payments_api'})-[:DEPENDS_ON*1..6]->(s:Service) "
        "RETURN collect(DISTINCT s.id)"
    )
    dependencies = set(res_dependencies.result_set[0][0])
    expected_dependencies = {
        "svc_ledger_db",
        "svc_fraud_service",
        "svc_event_bus",
        "svc_feature_store",
    }
    assert dependencies == expected_dependencies, (
        f"Transitive dependencies mismatch.\nGot: {dependencies}\nExpected: {expected_dependencies}\n"
        f"Diff: {dependencies ^ expected_dependencies}"
    )

    # 4. dec_029 SUPERSEDES dec_017
    res_supersedes = g.ro_query(
        "MATCH (d2:Decision {id: 'dec_029'})-[:SUPERSEDES]->(d1:Decision {id: 'dec_017'}) "
        "RETURN count(*)"
    )
    assert res_supersedes.result_set[0][0] == 1, "Expected dec_029 to SUPERSEDE dec_017"

    # 5. Priya has status on_leave
    res_priya = g.ro_query(
        "MATCH (p:Person {id: 'per_priya_nair'}) RETURN p.status"
    )
    assert res_priya.result_set and res_priya.result_set[0][0] == "on_leave", (
        f"Expected Priya Nair status to be 'on_leave', got {res_priya.result_set}"
    )
