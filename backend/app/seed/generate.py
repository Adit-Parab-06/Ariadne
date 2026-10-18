import json
import random
import time
from typing import Any

NOW = 1729180800000  # Fixed baseline epoch ms (approx Oct 17 2026) for determinism
DAY_MS = 86400000


def build_dataset(tenant: str) -> dict[str, Any]:
    """
    Builds synthetic dataset deterministically using random.Random(42).
    Returns dict containing lists of nodes and edges by type/label.
    """
    rng = random.Random(42)

    if tenant == "northwind":
        return _build_northwind(rng)
    elif tenant == "acme":
        return _build_acme(rng)
    else:
        raise ValueError(f"Unknown tenant: {tenant}")


def _build_northwind(rng: random.Random) -> dict[str, Any]:
    # --- TEAMS (6) ---
    teams = [
        {"id": "team_payments", "name": "Payments"},
        {"id": "team_platform", "name": "Platform"},
        {"id": "team_data", "name": "Data"},
        {"id": "team_growth", "name": "Growth"},
        {"id": "team_identity", "name": "Identity"},
        {"id": "team_infra", "name": "Infrastructure"},
    ]

    # --- HERO SERVICES (20) ---
    hero_services = [
        {"id": "svc_api_gateway", "name": "api-gateway", "kind": "edge", "tier": 0, "description": "API Gateway and ingress router", "team_id": "team_platform"},
        {"id": "svc_auth_service", "name": "auth-service", "kind": "service", "tier": 0, "description": "User authentication and JWT token validation", "team_id": "team_identity"},
        {"id": "svc_checkout_web", "name": "checkout-web", "kind": "frontend", "tier": 1, "description": "Web-based customer checkout flow interface", "team_id": "team_growth"},
        {"id": "svc_checkout_api", "name": "checkout-api", "kind": "service", "tier": 0, "description": "Cart and checkout orchestration engine", "team_id": "team_payments"},
        {"id": "svc_payments_api", "name": "payments-api", "kind": "service", "tier": 0, "description": "Card processing and payment authorization endpoint", "team_id": "team_payments"},
        {"id": "svc_ledger_db", "name": "ledger-db", "kind": "database", "tier": 0, "description": "Core transactional ledger and account balances PostgreSQL database", "team_id": "team_payments"},
        {"id": "svc_fraud_service", "name": "fraud-service", "kind": "service", "tier": 1, "description": "Real-time transaction risk evaluation service", "team_id": "team_payments"},
        {"id": "svc_feature_store", "name": "feature-store", "kind": "database", "tier": 2, "description": "Online feature store for machine learning models", "team_id": "team_data"},
        {"id": "svc_billing_worker", "name": "billing-worker", "kind": "worker", "tier": 1, "description": "Background worker processing recurring subscription charges", "team_id": "team_payments"},
        {"id": "svc_invoice_service", "name": "invoice-service", "kind": "service", "tier": 1, "description": "Billing receipt and invoice generator", "team_id": "team_payments"},
        {"id": "svc_notification_service", "name": "notification-service", "kind": "service", "tier": 2, "description": "Omnichannel customer notification dispatcher", "team_id": "team_growth"},
        {"id": "svc_email_gateway", "name": "email-gateway", "kind": "service", "tier": 2, "description": "Outbound email gateway for customer alerts", "team_id": "team_growth"},
        {"id": "svc_user_profile", "name": "user-profile-api", "kind": "service", "tier": 1, "description": "User profiles and organization accounts service", "team_id": "team_identity"},
        {"id": "svc_session_cache", "name": "session-cache", "kind": "cache", "tier": 1, "description": "Distributed Redis cache for user sessions", "team_id": "team_infra"},
        {"id": "svc_search_api", "name": "search-api", "kind": "service", "tier": 2, "description": "Catalog search and query auto-completion service", "team_id": "team_growth"},
        {"id": "svc_search_index", "name": "search-index", "kind": "database", "tier": 2, "description": "Elasticsearch cluster for product catalog", "team_id": "team_data"},
        {"id": "svc_analytics_pipeline", "name": "analytics-pipeline", "kind": "worker", "tier": 3, "description": "Clickstream and event ingestion pipeline", "team_id": "team_data"},
        {"id": "svc_event_bus", "name": "event-bus", "kind": "queue", "tier": 0, "description": "Kafka messaging backbone for asynchronous domain events", "team_id": "team_infra"},
        {"id": "svc_admin_console", "name": "admin-console", "kind": "frontend", "tier": 3, "description": "Internal operations and customer support web console", "team_id": "team_platform"},
        {"id": "svc_reporting_service", "name": "reporting-service", "kind": "service", "tier": 3, "description": "Internal metrics and management reports aggregator", "team_id": "team_data"},
    ]

    # --- FILLER SERVICES (7) ---
    filler_services = [
        {"id": "svc_fill_audit_log", "name": "audit-log", "kind": "service", "tier": 3, "description": "Security audit log collector", "team_id": "team_infra"},
        {"id": "svc_fill_metrics_agent", "name": "metrics-agent", "kind": "worker", "tier": 3, "description": "System telemetry collector", "team_id": "team_infra"},
        {"id": "svc_fill_crm_connector", "name": "crm-connector", "kind": "service", "tier": 3, "description": "Salesforce webhook synchronizer", "team_id": "team_growth"},
        {"id": "svc_fill_doc_portal", "name": "doc-portal", "kind": "frontend", "tier": 3, "description": "Customer developer documentation portal", "team_id": "team_platform"},
        {"id": "svc_fill_feedback_api", "name": "feedback-api", "kind": "service", "tier": 3, "description": "Customer NPS and survey API", "team_id": "team_growth"},
        {"id": "svc_fill_sandbox_runner", "name": "sandbox-runner", "kind": "worker", "tier": 3, "description": "Isolated developer code execution worker", "team_id": "team_platform"},
        {"id": "svc_fill_status_page", "name": "status-page", "kind": "frontend", "tier": 3, "description": "Public status dashboard", "team_id": "team_platform"},
    ]
    all_services = hero_services + filler_services

    # --- DEPENDS_ON (dependent -> dependency) ---
    # Hero dependencies exactly as specified:
    depends_on = [
        {"src": "svc_checkout_web", "dst": "svc_api_gateway"},
        {"src": "svc_checkout_web", "dst": "svc_checkout_api"},
        {"src": "svc_api_gateway", "dst": "svc_auth_service"},
        {"src": "svc_checkout_api", "dst": "svc_payments_api"},
        {"src": "svc_checkout_api", "dst": "svc_user_profile"},
        {"src": "svc_checkout_api", "dst": "svc_session_cache"},
        {"src": "svc_payments_api", "dst": "svc_ledger_db"},
        {"src": "svc_payments_api", "dst": "svc_fraud_service"},
        {"src": "svc_payments_api", "dst": "svc_event_bus"},
        {"src": "svc_fraud_service", "dst": "svc_feature_store"},
        {"src": "svc_billing_worker", "dst": "svc_ledger_db"},
        {"src": "svc_billing_worker", "dst": "svc_event_bus"},
        {"src": "svc_invoice_service", "dst": "svc_ledger_db"},
        {"src": "svc_invoice_service", "dst": "svc_email_gateway"},
        {"src": "svc_notification_service", "dst": "svc_event_bus"},
        {"src": "svc_notification_service", "dst": "svc_email_gateway"},
        {"src": "svc_user_profile", "dst": "svc_auth_service"},
        {"src": "svc_search_api", "dst": "svc_search_index"},
        {"src": "svc_search_api", "dst": "svc_auth_service"},
        {"src": "svc_analytics_pipeline", "dst": "svc_event_bus"},
        {"src": "svc_reporting_service", "dst": "svc_ledger_db"},
        {"src": "svc_reporting_service", "dst": "svc_analytics_pipeline"},
        {"src": "svc_admin_console", "dst": "svc_api_gateway"},
        {"src": "svc_admin_console", "dst": "svc_reporting_service"},
    ]
    # Filler dependencies (only among filler services):
    filler_depends = [
        {"src": "svc_fill_metrics_agent", "dst": "svc_fill_audit_log"},
        {"src": "svc_fill_crm_connector", "dst": "svc_fill_audit_log"},
        {"src": "svc_fill_doc_portal", "dst": "svc_fill_status_page"},
        {"src": "svc_fill_feedback_api", "dst": "svc_fill_audit_log"},
    ]
    depends_on.extend(filler_depends)

    # --- TEAM OWNS SERVICE ---
    owns = [{"team_id": s["team_id"], "service_id": s["id"]} for s in all_services]

    # --- PEOPLE (22 total) ---
    hero_people = [
        {"id": "per_priya_nair", "name": "Priya Nair", "role": "Staff SRE", "status": "on_leave", "team_id": "team_payments"},
        {"id": "per_dev_okafor", "name": "Dev Okafor", "role": "Senior Engineer", "status": "available", "team_id": "team_payments"},
        {"id": "per_mira_castillo", "name": "Mira Castillo", "role": "Engineering Manager", "status": "available", "team_id": "team_payments"},
    ]
    names_pool = [
        ("Liam Chen", "Senior Platform Engineer", "team_platform"),
        ("Aisha Patel", "Security Engineer", "team_identity"),
        ("Marcus Vance", "Data Architect", "team_data"),
        ("Elena Rostova", "Frontend Lead", "team_growth"),
        ("Kavita Rao", "Cloud Infra Specialist", "team_infra"),
        ("Carlos Mendes", "DevOps Engineer", "team_infra"),
        ("Chloe Bennett", "Product Designer", "team_growth"),
        ("Siddharth Joshi", "Backend Engineer", "team_payments"),
        ("Fatima Al-Mansoor", "Data Engineer", "team_data"),
        ("Hiroshi Tanaka", "Site Reliability Engineer", "team_platform"),
        ("Zoe Washington", "Staff Engineer", "team_platform"),
        ("Jonas Lindqvist", "Database Administrator", "team_data"),
        ("Ananya Sharma", "QA Engineer", "team_growth"),
        ("Mateo Garcia", "Systems Engineer", "team_infra"),
        ("Tariq Nabil", "Security Analyst", "team_identity"),
        ("Sara Lind", "Software Engineer", "team_identity"),
        ("Daniel Kim", "Platform Engineer", "team_platform"),
        ("Rachel Green", "Product Manager", "team_growth"),
        ("Arthur Dent", "Operations Engineer", "team_infra"),
    ]
    other_people = []
    for idx, (name, role, team_id) in enumerate(names_pool, start=1):
        slug = name.lower().replace(" ", "_").replace("-", "_")
        other_people.append({
            "id": f"per_{slug}",
            "name": name,
            "role": role,
            "status": "available",
            "team_id": team_id,
        })
    all_people = hero_people + other_people

    # --- MEMBER_OF (Person -> Team) ---
    member_of = [{"person_id": p["id"], "team_id": p["team_id"]} for p in all_people]

    # --- WORKED_ON COMMITS ---
    worked_on = [
        {"person_id": "per_priya_nair", "service_id": "svc_ledger_db", "commits": 212},
        {"person_id": "per_priya_nair", "service_id": "svc_payments_api", "commits": 88},
        {"person_id": "per_dev_okafor", "service_id": "svc_ledger_db", "commits": 97},
        {"person_id": "per_dev_okafor", "service_id": "svc_payments_api", "commits": 140},
        {"person_id": "per_mira_castillo", "service_id": "svc_payments_api", "commits": 12},
    ]
    # Non-hero commits on non-hero or filler services
    for p in other_people[:10]:
        worked_on.append({"person_id": p["id"], "service_id": "svc_fill_audit_log", "commits": rng.randint(5, 50)})

    # --- CUSTOMERS (14) ---
    hero_customers = [
        {"id": "cus_orbit_pay", "name": "Orbit Pay", "plan": "enterprise"},
        {"id": "cus_helios_retail", "name": "Helios Retail", "plan": "enterprise"},
        {"id": "cus_pinecrest_bank", "name": "Pinecrest Bank", "plan": "enterprise"},
    ]
    filler_customer_names = [
        "Apex Logistics", "Beacon Financial", "Catalyst Media", "Dynamo Health",
        "Echo Commerce", "Frontier SaaS", "Genesis Retail", "Horizon Telecom",
        "Ironclad Security", "Junction Labs", "Keystone Capital",
    ]
    other_customers = []
    for name in filler_customer_names:
        cid = "cus_" + name.lower().replace(" ", "_")
        other_customers.append({"id": cid, "name": name, "plan": rng.choice(["starter", "growth", "business"])})
    all_customers = hero_customers + other_customers

    # --- USES (Customer -> Service) ---
    uses = []
    for c in hero_customers:
        uses.append({"customer_id": c["id"], "service_id": "svc_checkout_web"})
        uses.append({"customer_id": c["id"], "service_id": "svc_payments_api"})
    for c in other_customers:
        target_svc = rng.choice(["svc_search_api", "svc_fill_doc_portal", "svc_fill_feedback_api"])
        uses.append({"customer_id": c["id"], "service_id": target_svc})

    # --- DOCS (12 total: 4 hero + 8 filler) ---
    hero_docs = [
        {
            "id": "doc_rb_ledger_pool",
            "title": "Ledger connection pool saturation",
            "kind": "runbook",
            "body": "1. Inspect pgbouncer pools for waiting clients.\n2. Compare max_client_conn to worker concurrency.\n3. Raise the limit and reload pgbouncer.\n4. Verify p99 and 5xx recover.",
            "service_id": "svc_ledger_db",
        },
        {
            "id": "doc_adr_017",
            "title": "ADR 017: Initial PgBouncer Pool Sizing",
            "kind": "adr",
            "body": "ADR 017 sets the initial pgbouncer pool_size to 50 connections to protect PostgreSQL from overloading.",
            "service_id": "svc_ledger_db",
        },
        {
            "id": "doc_adr_029",
            "title": "ADR 029: Scaled PgBouncer Connection Pool for Ledger",
            "kind": "adr",
            "body": "ADR 029 increases pgbouncer pool_size to 120 and sets max_client_conn to accommodate higher peak worker concurrency.",
            "service_id": "svc_ledger_db",
        },
        {
            "id": "doc_pm_2041",
            "title": "Postmortem: payments-api p99 latency spike and elevated 5xx",
            "kind": "postmortem",
            "body": "Detailed postmortem on incident inc_2041 regarding PgBouncer pool saturation on ledger-db after scaling checkout workers.",
            "service_id": "svc_ledger_db",
        },
    ]
    filler_docs = []
    for i in range(1, 9):
        filler_docs.append({
            "id": f"doc_fill_{i:03d}",
            "title": f"Operations guide for filler subsystem {i}",
            "kind": rng.choice(["runbook", "adr", "postmortem"]),
            "body": f"Standard operational procedures and troubleshooting guidelines for subsystem {i}.",
            "service_id": "svc_fill_audit_log",
        })
    all_docs = hero_docs + filler_docs

    # --- THREADS (20 total: 1 hero + 19 filler) ---
    hero_threads = [
        {
            "id": "thr_0412",
            "channel": "#payments-eng",
            "summary": "Engineering discussion on increasing ledger-db pgbouncer pool size to 120 to resolve connection exhaustion",
            "ts": NOW - (41 * DAY_MS),
            "service_id": "svc_ledger_db",
        }
    ]
    filler_threads = []
    for i in range(1, 20):
        filler_threads.append({
            "id": f"thr_fill_{i:04d}",
            "channel": "#infra-general",
            "summary": f"Routine channel chatter and maintenance notes for cluster {i}",
            "ts": NOW - (rng.randint(5, 60) * DAY_MS),
            "service_id": "svc_fill_audit_log",
        })
    all_threads = hero_threads + filler_threads

    # --- DECISIONS (8 total: 2 hero + 6 filler) ---
    hero_decisions = [
        {
            "id": "dec_017",
            "title": "Set pgbouncer pool_size to 50",
            "rationale": "Initial conservative connection limits for early architecture",
            "decided_at": NOW - (180 * DAY_MS),
            "status": "superseded",
            "service_id": "svc_ledger_db",
            "author_id": "per_priya_nair",
            "doc_id": "doc_adr_017",
            "thread_id": None,
        },
        {
            "id": "dec_029",
            "title": "Set pgbouncer pool_size to 120",
            "rationale": "Scale pool size to handle increased worker concurrency without dropping client requests",
            "decided_at": NOW - (40 * DAY_MS),
            "status": "active",
            "service_id": "svc_ledger_db",
            "author_id": "per_dev_okafor",
            "doc_id": "doc_adr_029",
            "thread_id": "thr_0412",
        },
    ]
    filler_decisions = []
    for i in range(1, 7):
        filler_decisions.append({
            "id": f"dec_fill_{i:03d}",
            "title": f"Decision on filler subsystem configuration {i}",
            "rationale": "Routine optimization for peripheral services",
            "decided_at": NOW - (rng.randint(30, 120) * DAY_MS),
            "status": "active",
            "service_id": "svc_fill_audit_log",
            "author_id": other_people[0]["id"],
            "doc_id": filler_docs[0]["id"],
            "thread_id": filler_threads[0]["id"],
        })
    all_decisions = hero_decisions + filler_decisions

    # --- INCIDENTS (30 total) ---
    hero_inc_2041 = {
        "id": "inc_2041",
        "title": "payments-api p99 latency spike and elevated 5xx",
        "severity": "SEV2",
        "started_at": NOW - (25 * DAY_MS),
        "resolved_at": NOW - (25 * DAY_MS) + 7200000,
        "summary": "Connection pool saturation at the ledger-db pgbouncer after a deploy raised worker concurrency. Raising max_client_conn and reloading pgbouncer restored latency.",
        "affected": ["svc_payments_api", "svc_checkout_api", "svc_ledger_db"],
        "root_cause_in": "svc_ledger_db",
        "resolved_by": "per_priya_nair",
        "resolved_with": "doc_rb_ledger_pool",
    }
    hero_inc_1988 = {
        "id": "inc_1988",
        "title": "ledger-db slow queries after schema migration",
        "severity": "SEV3",
        "started_at": NOW - (60 * DAY_MS),
        "resolved_at": NOW - (60 * DAY_MS) + 3600000,
        "summary": "Post-migration index rebuild caused temporary lock contention on ledger-db tables.",
        "affected": ["svc_ledger_db"],
        "root_cause_in": "svc_ledger_db",
        "resolved_by": "per_dev_okafor",
        "resolved_with": None,
    }
    hero_inc_1850 = {
        "id": "inc_1850",
        "title": "ledger-db replication lag",
        "severity": "SEV3",
        "started_at": NOW - (90 * DAY_MS),
        "resolved_at": NOW - (90 * DAY_MS) + 4000000,
        "summary": "Read-replica network packet drop caused replication lag on ledger-db follower instance.",
        "affected": ["svc_ledger_db"],
        "root_cause_in": "svc_ledger_db",
        "resolved_by": "per_priya_nair",
        "resolved_with": None,
    }
    hero_inc_2102 = {
        "id": "inc_2102",
        "title": "search-api latency",
        "severity": "SEV3",
        "started_at": NOW - (15 * DAY_MS),
        "resolved_at": NOW - (15 * DAY_MS) + 3000000,
        "summary": "Elasticsearch heap exhaustion during index rebalancing.",
        "affected": ["svc_search_api"],
        "root_cause_in": "svc_search_index",
        "resolved_by": other_people[2]["id"],
        "resolved_with": None,
    }
    all_incidents = [hero_inc_2041, hero_inc_1988, hero_inc_1850, hero_inc_2102]
    for i in range(1, 27):
        all_incidents.append({
            "id": f"inc_fill_{i:04d}",
            "title": f"Telemetry drop and intermittent lag in cluster {i}",
            "severity": rng.choice(["SEV3", "SEV4"]),
            "started_at": NOW - (rng.randint(10, 150) * DAY_MS),
            "resolved_at": NOW - (rng.randint(10, 150) * DAY_MS) + 3600000,
            "summary": f"Resolved transient issue in peripheral component {i} by service bounce.",
            "affected": ["svc_fill_audit_log"],
            "root_cause_in": "svc_fill_audit_log",
            "resolved_by": other_people[i % len(other_people)]["id"],
            "resolved_with": None,
        })

    # --- TICKETS (40 total) ---
    hero_ticket = {
        "id": "tkt_orbit_timeouts",
        "title": "Orbit Pay: intermittent payment timeouts",
        "customer_id": "cus_orbit_pay",
        "service_id": "svc_payments_api",
        "relates_to_incident": "inc_2041",
        "assigned_to": "per_priya_nair",
        "status": "resolved",
        "created_at": NOW - (25 * DAY_MS),
        "resolved_at": NOW - (25 * DAY_MS) + 7200000,
    }
    all_tickets = [hero_ticket]
    for i in range(1, 40):
        cust = rng.choice(all_customers)
        all_tickets.append({
            "id": f"tkt_fill_{i:04d}",
            "title": f"Inquiry regarding service latency {i}",
            "customer_id": cust["id"],
            "service_id": rng.choice(["svc_checkout_web", "svc_search_api", "svc_fill_feedback_api"]),
            "relates_to_incident": None,
            "assigned_to": rng.choice(other_people)["id"],
            "status": rng.choice(["resolved", "closed", "open"]),
            "created_at": NOW - (rng.randint(1, 60) * DAY_MS),
            "resolved_at": NOW - (rng.randint(1, 30) * DAY_MS),
        })

    # --- MEMORY SEEDS (northwind only) ---
    memory_facts = [
        {
            "id": "fct_ledger_pgb_200",
            "subject_id": "svc_ledger_db",
            "predicate": "pgbouncer_max_client_conn",
            "text": "ledger-db pgbouncer max_client_conn is 200",
            "confidence": 0.98,
            "valid_from": NOW - (25 * DAY_MS),
            "valid_to": 0,
        }
    ]
    memory_procedures = [
        {
            "id": "prc_ledger_pool",
            "name": "Ledger pool saturation response",
            "trigger_text": "payments-api p99 latency spike and elevated 5xx errors",
            "steps": json.dumps([
                "1. Inspect pgbouncer pools for waiting clients.",
                "2. Compare max_client_conn to worker concurrency.",
                "3. Raise the limit and reload pgbouncer.",
                "4. Verify p99 and 5xx recover.",
            ]),
            "success_count": 1,
            "fail_count": 0,
            "last_used": NOW - (25 * DAY_MS),
            "service_id": "svc_ledger_db",
        }
    ]
    memory_episodes = [
        {
            "id": "epi_2041",
            "run_id": "run_seed_2041",
            "goal": "Resolve payments-api latency spike and 5xx errors",
            "outcome": "success",
            "summary": "Resolved connection pool saturation at ledger-db pgbouncer by raising max_client_conn and reloading configuration.",
            "ts": NOW - (25 * DAY_MS),
            "incident_id": "inc_2041",
            "service_id": "svc_ledger_db",
            "procedure_id": "prc_ledger_pool",
            "produced_fact_id": "fct_ledger_pgb_200",
        }
    ]

    return {
        "teams": teams,
        "services": all_services,
        "depends_on": depends_on,
        "owns": owns,
        "people": all_people,
        "member_of": member_of,
        "worked_on": worked_on,
        "customers": all_customers,
        "uses": uses,
        "docs": all_docs,
        "threads": all_threads,
        "decisions": all_decisions,
        "incidents": all_incidents,
        "tickets": all_tickets,
        "facts": memory_facts,
        "procedures": memory_procedures,
        "episodes": memory_episodes,
    }


def _build_acme(rng: random.Random) -> dict[str, Any]:
    """Small isolated dataset for Acme tenant: 8 services, 6 people, 4 incidents, 3 docs, 2 customers."""
    teams = [
        {"id": "team_acme_core", "name": "Acme Core Team"},
        {"id": "team_acme_ops", "name": "Acme Ops"},
    ]
    services = [
        {"id": "svc_acme_web", "name": "acme-web", "kind": "frontend", "tier": 0, "description": "Acme storefront UI", "team_id": "team_acme_core"},
        {"id": "svc_acme_api", "name": "acme-api", "kind": "service", "tier": 0, "description": "Acme primary API gateway", "team_id": "team_acme_core"},
        {"id": "svc_acme_auth", "name": "acme-auth", "kind": "service", "tier": 0, "description": "Acme authentication service", "team_id": "team_acme_core"},
        {"id": "svc_acme_db", "name": "acme-db", "kind": "database", "tier": 0, "description": "Acme MySQL cluster", "team_id": "team_acme_ops"},
        {"id": "svc_acme_cache", "name": "acme-cache", "kind": "cache", "tier": 1, "description": "Acme Memcached", "team_id": "team_acme_ops"},
        {"id": "svc_acme_worker", "name": "acme-worker", "kind": "worker", "tier": 1, "description": "Acme order queue worker", "team_id": "team_acme_core"},
        {"id": "svc_acme_notify", "name": "acme-notify", "kind": "service", "tier": 2, "description": "Acme SMS notifier", "team_id": "team_acme_core"},
        {"id": "svc_acme_analytics", "name": "acme-analytics", "kind": "worker", "tier": 3, "description": "Acme batch analytics", "team_id": "team_acme_ops"},
    ]
    depends_on = [
        {"src": "svc_acme_web", "dst": "svc_acme_api"},
        {"src": "svc_acme_api", "dst": "svc_acme_auth"},
        {"src": "svc_acme_api", "dst": "svc_acme_db"},
        {"src": "svc_acme_api", "dst": "svc_acme_cache"},
        {"src": "svc_acme_worker", "dst": "svc_acme_db"},
        {"src": "svc_acme_worker", "dst": "svc_acme_notify"},
        {"src": "svc_acme_analytics", "dst": "svc_acme_db"},
    ]
    owns = [{"team_id": s["team_id"], "service_id": s["id"]} for s in services]
    people = [
        {"id": "per_acme_alice", "name": "Alice Smith", "role": "Lead Architect", "status": "available", "team_id": "team_acme_core"},
        {"id": "per_acme_bob", "name": "Bob Jones", "role": "Site Reliability Engineer", "status": "available", "team_id": "team_acme_ops"},
        {"id": "per_acme_charlie", "name": "Charlie Brown", "role": "Backend Engineer", "status": "available", "team_id": "team_acme_core"},
        {"id": "per_acme_diana", "name": "Diana Prince", "role": "DevOps Engineer", "status": "available", "team_id": "team_acme_ops"},
        {"id": "per_acme_evan", "name": "Evan Wright", "role": "QA Lead", "status": "available", "team_id": "team_acme_core"},
        {"id": "per_acme_fiona", "name": "Fiona Gallagher", "role": "Product Manager", "status": "available", "team_id": "team_acme_core"},
    ]
    member_of = [{"person_id": p["id"], "team_id": p["team_id"]} for p in people]
    customers = [
        {"id": "cus_acme_corp1", "name": "Beta Enterprises", "plan": "enterprise"},
        {"id": "cus_acme_corp2", "name": "Gamma Solutions", "plan": "growth"},
    ]
    uses = [
        {"customer_id": "cus_acme_corp1", "service_id": "svc_acme_web"},
        {"customer_id": "cus_acme_corp2", "service_id": "svc_acme_web"},
    ]
    docs = [
        {"id": "doc_acme_runbook_1", "title": "Acme Database Failover Runbook", "kind": "runbook", "body": "Steps to promote MySQL read replica to primary.", "service_id": "svc_acme_db"},
        {"id": "doc_acme_adr_1", "title": "ADR 001: Memcached caching policy", "kind": "adr", "body": "TTL guidelines for session tokens.", "service_id": "svc_acme_cache"},
        {"id": "doc_acme_pm_1", "title": "Postmortem: SMS delivery delay", "kind": "postmortem", "body": "Postmortem regarding third-party SMS vendor outage.", "service_id": "svc_acme_notify"},
    ]
    incidents = [
        {"id": "inc_acme_01", "title": "Acme API latency spike", "severity": "SEV2", "started_at": NOW - (10 * DAY_MS), "resolved_at": NOW - (10 * DAY_MS) + 3600000, "summary": "Memcached eviction surge caused API latency increase.", "affected": ["svc_acme_api", "svc_acme_cache"], "root_cause_in": "svc_acme_cache", "resolved_by": "per_acme_bob", "resolved_with": "doc_acme_runbook_1"},
        {"id": "inc_acme_02", "title": "Order queue lag", "severity": "SEV3", "started_at": NOW - (20 * DAY_MS), "resolved_at": NOW - (20 * DAY_MS) + 1800000, "summary": "Worker thread deadlock.", "affected": ["svc_acme_worker"], "root_cause_in": "svc_acme_worker", "resolved_by": "per_acme_charlie", "resolved_with": None},
        {"id": "inc_acme_03", "title": "Analytics slow query", "severity": "SEV4", "started_at": NOW - (30 * DAY_MS), "resolved_at": NOW - (30 * DAY_MS) + 5400000, "summary": "Large report scan.", "affected": ["svc_acme_analytics"], "root_cause_in": "svc_acme_db", "resolved_by": "per_acme_diana", "resolved_with": None},
        {"id": "inc_acme_04", "title": "Auth token verification failure", "severity": "SEV2", "started_at": NOW - (40 * DAY_MS), "resolved_at": NOW - (40 * DAY_MS) + 2400000, "summary": "Expired signing key.", "affected": ["svc_acme_auth"], "root_cause_in": "svc_acme_auth", "resolved_by": "per_acme_alice", "resolved_with": None},
    ]

    return {
        "teams": teams,
        "services": services,
        "depends_on": depends_on,
        "owns": owns,
        "people": people,
        "member_of": member_of,
        "worked_on": [],
        "customers": customers,
        "uses": uses,
        "docs": docs,
        "threads": [],
        "decisions": [],
        "incidents": incidents,
        "tickets": [],
        "facts": [],
        "procedures": [],
        "episodes": [],
    }
