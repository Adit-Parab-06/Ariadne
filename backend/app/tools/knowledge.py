import time
from typing import Any, Dict, List, Optional

from app.db import graph_for
from app.tools import tool
from app.tools.evidence import Evidence, ToolResult


@tool(
    name="resolve_service",
    description="Resolves a service name or identifier to service nodes in the knowledge graph.",
    params={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Partial or full service name or ID"}
        },
        "required": ["query"],
    },
    agents=["scout", "archivist"],
    readonly=True,
)
def resolve_service(tenant: str, query: str) -> ToolResult:
    g = graph_for(tenant)
    cypher = (
        "MATCH (s:Service) "
        "WHERE toLower(s.name) CONTAINS toLower($q) OR toLower(s.id) CONTAINS toLower($q) "
        "RETURN s.id AS id, s.name AS name, s.kind AS kind, s.tier AS tier, s.description AS description "
        "LIMIT 5"
    )
    res = g.ro_query(cypher, {"q": query})
    rows = res.result_set or []

    evidence = Evidence()
    matches = []
    for row in rows:
        sid, sname, skind, stier, sdesc = row[0], row[1], row[2], row[3], row[4]
        matches.append({
            "id": sid,
            "name": sname,
            "kind": skind,
            "tier": stier,
            "description": sdesc,
        })
        evidence.add_node(sid, "Service", sname)

    summary = f"Found {len(matches)} service(s) matching '{query}'"
    return ToolResult(
        summary=summary,
        data={"matches": matches},
        evidence=evidence,
        cypher=[cypher],
    )


@tool(
    name="blast_radius",
    description="Computes blast radius or dependencies of a service. 'dependents' gives upstream impacted services and customers; 'dependencies' gives downstream services it relies on.",
    params={
        "type": "object",
        "properties": {
            "service_id": {"type": "string", "description": "Service ID"},
            "direction": {
                "type": "string",
                "enum": ["dependents", "dependencies"],
                "default": "dependents",
                "description": "'dependents' for upstream impact; 'dependencies' for downstream suspects",
            },
            "max_hops": {
                "type": "integer",
                "default": 4,
                "description": "Max hops (1-6)",
            },
        },
        "required": ["service_id"],
    },
    agents=["scout"],
    readonly=True,
)
def blast_radius(
    tenant: str, service_id: str, direction: str = "dependents", max_hops: int = 4
) -> ToolResult:
    g = graph_for(tenant)
    hops = max(1, min(int(max_hops), 6))
    evidence = Evidence()
    cyphers: List[str] = []

    # Get root service name for evidence
    root_res = g.ro_query("MATCH (s:Service {id: $sid}) RETURN s.name", {"sid": service_id})
    root_name = root_res.result_set[0][0] if root_res.result_set else service_id
    evidence.add_node(service_id, "Service", root_name)

    services_data = []
    all_sids = [service_id]

    if direction == "dependents":
        # Dependent -> Dependency, so: (s)-[:DEPENDS_ON*1..hops]->(root)
        cypher = (
            f"MATCH (x:Service {{id: $sid}}) "
            f"MATCH p = (s:Service)-[:DEPENDS_ON*1..{hops}]->(x) "
            f"WITH s, min(length(p)) AS hops "
            f"OPTIONAL MATCH (c:Customer)-[:USES]->(s) "
            f"RETURN s.id AS id, s.name AS name, s.tier AS tier, hops, collect(DISTINCT c.name) AS customers "
            f"ORDER BY hops, name"
        )
        cyphers.append(cypher)
        res = g.ro_query(cypher, {"sid": service_id})
        for row in res.result_set or []:
            sid, sname, stier, hops_val, scust = row[0], row[1], row[2], row[3], row[4]
            services_data.append({
                "id": sid,
                "name": sname,
                "tier": stier,
                "hops": hops_val,
                "customers": scust,
            })
            all_sids.append(sid)
            evidence.add_node(sid, "Service", sname)
            for cname in scust:
                evidence.add_node(f"cus_{cname.lower().replace(' ', '_')}", "Customer", cname)
    else:
        # (root)-[:DEPENDS_ON*1..hops]->(s)
        cypher = (
            f"MATCH (x:Service {{id: $sid}}) "
            f"MATCH p = (x)-[:DEPENDS_ON*1..{hops}]->(s:Service) "
            f"WITH s, min(length(p)) AS hops "
            f"RETURN s.id AS id, s.name AS name, s.tier AS tier, hops "
            f"ORDER BY hops, name"
        )
        cyphers.append(cypher)
        res = g.ro_query(cypher, {"sid": service_id})
        for row in res.result_set or []:
            sid, sname, stier, hops_val = row[0], row[1], row[2], row[3]
            services_data.append({
                "id": sid,
                "name": sname,
                "tier": stier,
                "hops": hops_val,
            })
            all_sids.append(sid)
            evidence.add_node(sid, "Service", sname)

    # Fetch edges between the involved services
    edge_cypher = (
        "MATCH (s1:Service)-[r:DEPENDS_ON]->(s2:Service) "
        "WHERE s1.id IN $ids AND s2.id IN $ids "
        "RETURN s1.id, s2.id"
    )
    cyphers.append(edge_cypher)
    edge_res = g.ro_query(edge_cypher, {"ids": all_sids})
    for erow in edge_res.result_set or []:
        evidence.add_edge(erow[0], "DEPENDS_ON", erow[1])

    summary = (
        f"Blast radius ({direction}) for {service_id}: found {len(services_data)} service(s) within {hops} hops"
    )
    return ToolResult(
        summary=summary,
        data={
            "service_id": service_id,
            "direction": direction,
            "count": len(services_data),
            "services": services_data,
        },
        evidence=evidence,
        cypher=cyphers,
    )


@tool(
    name="service_criticality",
    description="Ranks services by topological criticality using PageRank over service dependencies.",
    params={
        "type": "object",
        "properties": {
            "top_k": {"type": "integer", "default": 5, "description": "Number of top critical services"}
        },
        "required": [],
    },
    agents=["scout"],
    readonly=True,
)
def service_criticality(tenant: str, top_k: int = 5) -> ToolResult:
    g = graph_for(tenant)
    k = max(1, min(int(top_k), 20))
    cypher = (
        "CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score "
        "RETURN node.id AS id, node.name AS name, node.tier AS tier, score "
        "ORDER BY score DESC LIMIT $k"
    )
    res = g.ro_query(cypher, {"k": k})
    rows = res.result_set or []

    evidence = Evidence()
    rankings = []
    for rank, row in enumerate(rows, start=1):
        sid, sname, stier, score = row[0], row[1], row[2], row[3]
        rankings.append({
            "rank": rank,
            "id": sid,
            "name": sname,
            "tier": stier,
            "score": round(float(score), 4),
        })
        evidence.add_node(sid, "Service", sname)

    summary = f"Top {len(rankings)} critical services ranked by PageRank"
    return ToolResult(
        summary=summary,
        data={"criticality": rankings},
        evidence=evidence,
        cypher=[cypher],
    )


@tool(
    name="choke_points",
    description="Identifies single-point-of-failure bottlenecks using Betweenness Centrality over the dependency graph.",
    params={
        "type": "object",
        "properties": {
            "top_k": {"type": "integer", "default": 5, "description": "Number of choke points"}
        },
        "required": [],
    },
    agents=["scout"],
    readonly=True,
)
def choke_points(tenant: str, top_k: int = 5) -> ToolResult:
    g = graph_for(tenant)
    k = max(1, min(int(top_k), 20))
    cypher = (
        "CALL algo.betweenness({nodeLabels: ['Service'], relationshipTypes: ['DEPENDS_ON']}) YIELD node, score "
        "RETURN node.id AS id, node.name AS name, node.tier AS tier, score "
        "ORDER BY score DESC LIMIT $k"
    )
    res = g.ro_query(cypher, {"k": k})
    rows = res.result_set or []

    evidence = Evidence()
    choke_list = []
    for rank, row in enumerate(rows, start=1):
        sid, sname, stier, score = row[0], row[1], row[2], row[3]
        choke_list.append({
            "rank": rank,
            "id": sid,
            "name": sname,
            "tier": stier,
            "score": round(float(score), 4),
        })
        evidence.add_node(sid, "Service", sname)

    summary = f"Top {len(choke_list)} architectural choke points"
    return ToolResult(
        summary=summary,
        data={"choke_points": choke_list},
        evidence=evidence,
        cypher=[cypher],
    )


@tool(
    name="dependency_path",
    description="Finds the shortest dependency path between two services.",
    params={
        "type": "object",
        "properties": {
            "from_id": {"type": "string", "description": "Origin service ID"},
            "to_id": {"type": "string", "description": "Target service ID"},
        },
        "required": ["from_id", "to_id"],
    },
    agents=["scout"],
    readonly=True,
)
def dependency_path(tenant: str, from_id: str, to_id: str) -> ToolResult:
    g = graph_for(tenant)
    evidence = Evidence()
    cyphers: List[str] = []

    # FalkorDB requirement: shortestPath in WITH or RETURN clause
    cypher_forward = (
        "MATCH (a:Service {id: $fid}), (b:Service {id: $tid}) "
        "WITH shortestPath((a)-[:DEPENDS_ON*]->(b)) AS p "
        "RETURN [n IN nodes(p) | n.id] AS ids"
    )
    cyphers.append(cypher_forward)
    res = g.ro_query(cypher_forward, {"fid": from_id, "tid": to_id})

    node_ids: List[str] = []
    if res.result_set and res.result_set[0][0]:
        node_ids = res.result_set[0][0]
    else:
        # Try reverse direction
        cypher_reverse = (
            "MATCH (a:Service {id: $tid}), (b:Service {id: $fid}) "
            "WITH shortestPath((a)-[:DEPENDS_ON*]->(b)) AS p "
            "RETURN [n IN nodes(p) | n.id] AS ids"
        )
        cyphers.append(cypher_reverse)
        res_rev = g.ro_query(cypher_reverse, {"fid": from_id, "tid": to_id})
        if res_rev.result_set and res_rev.result_set[0][0]:
            node_ids = res_rev.result_set[0][0]

    if not node_ids:
        return ToolResult(
            summary=f"No dependency path found between {from_id} and {to_id}",
            data={"path": [], "length": 0},
            evidence=evidence,
            cypher=cyphers,
        )

    # Fetch names for nodes
    name_res = g.ro_query("MATCH (s:Service) WHERE s.id IN $ids RETURN s.id, s.name", {"ids": node_ids})
    name_map = {row[0]: row[1] for row in (name_res.result_set or [])}

    for nid in node_ids:
        evidence.add_node(nid, "Service", name_map.get(nid, nid))

    for i in range(len(node_ids) - 1):
        evidence.add_edge(node_ids[i], "DEPENDS_ON", node_ids[i + 1])

    summary = f"Shortest dependency path: {' -> '.join(node_ids)} ({len(node_ids) - 1} hops)"
    return ToolResult(
        summary=summary,
        data={"path": node_ids, "length": len(node_ids) - 1},
        evidence=evidence,
        cypher=cyphers,
    )


@tool(
    name="find_experts",
    description="Ranks subject-matter experts for a service by commit history, incident resolutions, and team ownership. Distinguishes available experts from those on leave.",
    params={
        "type": "object",
        "properties": {
            "service_id": {"type": "string", "description": "Service ID"},
            "k": {"type": "integer", "default": 3, "description": "Number of experts to return"},
        },
        "required": ["service_id"],
    },
    agents=["archivist"],
    readonly=True,
)
def find_experts(tenant: str, service_id: str, k: int = 3) -> ToolResult:
    g = graph_for(tenant)
    evidence = Evidence()
    cypher = (
        "MATCH (x:Service {id: $sid}) "
        "MATCH (p:Person) "
        "OPTIONAL MATCH (p)-[w:WORKED_ON]->(x) "
        "OPTIONAL MATCH (p)-[:RESOLVED]->(i:Incident)-[:AFFECTED]->(x) "
        "OPTIONAL MATCH (p)-[:MEMBER_OF]->(t:Team)-[:OWNS]->(x) "
        "WITH p, max(coalesce(w.commits, 0)) AS commits, count(DISTINCT i) AS resolved, count(DISTINCT t) AS owner_team "
        "WHERE commits > 0 OR resolved > 0 OR owner_team > 0 "
        "RETURN p.id AS id, p.name AS name, p.status AS status, commits, resolved, owner_team"
    )
    res = g.ro_query(cypher, {"sid": service_id})
    rows = res.result_set or []

    # Get service node for evidence
    s_res = g.ro_query("MATCH (s:Service {id: $sid}) RETURN s.name", {"sid": service_id})
    s_name = s_res.result_set[0][0] if s_res.result_set else service_id
    evidence.add_node(service_id, "Service", s_name)

    candidates = []
    for row in rows:
        pid, pname, pstatus, commits, resolved, owner_team = (
            row[0],
            row[1],
            row[2],
            int(row[3]),
            int(row[4]),
            int(row[5]),
        )
        score = 3 * resolved + 0.1 * commits + 2 * owner_team
        candidates.append({
            "id": pid,
            "name": pname,
            "status": pstatus,
            "commits": commits,
            "resolved": resolved,
            "owner_team": owner_team,
            "score": round(score, 2),
        })

    # Sort descending by score
    candidates.sort(key=lambda c: c["score"], reverse=True)

    recommended = None
    skipped = []
    for c in candidates:
        evidence.add_node(c["id"], "Person", c["name"])
        if c["status"] == "available":
            if recommended is None:
                recommended = c
        elif c["status"] == "on_leave":
            skipped.append(c)

    # Add evidence edges for candidates
    rel_cypher = (
        "MATCH (p:Person)-[w:WORKED_ON]->(x:Service {id: $sid}) "
        "RETURN p.id, type(w), x.id"
    )
    rel_res = g.ro_query(rel_cypher, {"sid": service_id})
    for r in rel_res.result_set or []:
        evidence.add_edge(r[0], r[1], r[2])

    summary = (
        f"Found {len(candidates)} expert(s) for {service_id}. "
        f"Recommended: {recommended['name'] if recommended else 'None'} "
        f"(Skipped on-leave: {', '.join([s['name'] for s in skipped]) if skipped else 'None'})"
    )
    return ToolResult(
        summary=summary,
        data={
            "service_id": service_id,
            "ranked": candidates[:k],
            "recommended": recommended,
            "skipped": skipped,
        },
        evidence=evidence,
        cypher=[cypher, rel_cypher],
    )


@tool(
    name="customer_history",
    description="Retrieves customer support tickets and related incidents within a lookback window.",
    params={
        "type": "object",
        "properties": {
            "customer_query": {"type": "string", "description": "Customer name or ID"},
            "days": {"type": "integer", "default": 30, "description": "Lookback window in days"},
        },
        "required": ["customer_query"],
    },
    agents=["scout"],
    readonly=True,
)
def customer_history(tenant: str, customer_query: str, days: int = 30) -> ToolResult:
    g = graph_for(tenant)
    evidence = Evidence()
    cypher = (
        "MATCH (c:Customer) "
        "WHERE toLower(c.name) CONTAINS toLower($q) OR toLower(c.id) CONTAINS toLower($q) "
        "MATCH (c)-[:RAISED]->(t:Ticket) "
        "OPTIONAL MATCH (t)-[:RELATES_TO]->(i:Incident) "
        "OPTIONAL MATCH (t)-[:ABOUT]->(s:Service) "
        "RETURN c.id AS customer_id, c.name AS customer_name, t.id AS ticket_id, t.title AS ticket_title, "
        "t.status AS status, t.created_at AS created_at, i.id AS incident_id, i.title AS incident_title, "
        "s.id AS service_id, s.name AS service_name "
        "ORDER BY t.created_at DESC"
    )
    res = g.ro_query(cypher, {"q": customer_query})
    rows = res.result_set or []

    tickets = []
    for row in rows:
        cid, cname, tid, ttitle, status, cat, iid, ititle, sid, sname = row
        tickets.append({
            "ticket_id": tid,
            "title": ttitle,
            "status": status,
            "created_at": cat,
            "customer_id": cid,
            "customer_name": cname,
            "incident_id": iid,
            "incident_title": ititle,
            "service_id": sid,
            "service_name": sname,
        })
        evidence.add_node(cid, "Customer", cname)
        evidence.add_node(tid, "Ticket", ttitle)
        evidence.add_edge(cid, "RAISED", tid)
        if iid:
            evidence.add_node(iid, "Incident", ititle)
            evidence.add_edge(tid, "RELATES_TO", iid)
        if sid:
            evidence.add_node(sid, "Service", sname)
            evidence.add_edge(tid, "ABOUT", sid)

    summary = f"Found {len(tickets)} ticket(s) for customer query '{customer_query}'"
    return ToolResult(
        summary=summary,
        data={"tickets": tickets},
        evidence=evidence,
        cypher=[cypher],
    )


@tool(
    name="trace_decision",
    description="Traces active and superseded architectural decisions (ADRs) for a service, including authors, documents, and discussions.",
    params={
        "type": "object",
        "properties": {
            "service_id": {"type": "string", "description": "Service ID"},
        },
        "required": ["service_id"],
    },
    agents=["archivist"],
    readonly=True,
)
def trace_decision(tenant: str, service_id: str) -> ToolResult:
    g = graph_for(tenant)
    evidence = Evidence()
    cyphers: List[str] = []

    # 1. Active decision
    cypher_active = (
        "MATCH (s:Service {id: $sid})<-[:ABOUT]-(dec:Decision {status: 'active'}) "
        "OPTIONAL MATCH (p:Person)-[:AUTHORED]->(dec) "
        "OPTIONAL MATCH (dec)-[:RECORDED_IN]->(doc:Doc) "
        "OPTIONAL MATCH (dec)-[:DISCUSSED_IN]->(thr:Thread) "
        "RETURN dec.id, dec.title, dec.rationale, dec.decided_at, dec.status, "
        "p.id, p.name, doc.id, doc.title, thr.id, thr.channel"
    )
    cyphers.append(cypher_active)
    res_act = g.ro_query(cypher_active, {"sid": service_id})
    rows = res_act.result_set or []

    if not rows:
        return ToolResult(
            summary=f"No active decision found for {service_id}",
            data={"active": None, "lineage": []},
            evidence=evidence,
            cypher=cyphers,
        )

    act_row = rows[0]
    active_dec = {
        "id": act_row[0],
        "title": act_row[1],
        "rationale": act_row[2],
        "decided_at": act_row[3],
        "status": act_row[4],
        "author_id": act_row[5],
        "author_name": act_row[6],
        "doc_id": act_row[7],
        "doc_title": act_row[8],
        "thread_id": act_row[9],
        "thread_channel": act_row[10],
    }
    evidence.add_node(active_dec["id"], "Decision", active_dec["title"])
    if active_dec["author_id"]:
        evidence.add_node(active_dec["author_id"], "Person", active_dec["author_name"])
        evidence.add_edge(active_dec["author_id"], "AUTHORED", active_dec["id"])
    if active_dec["doc_id"]:
        evidence.add_node(active_dec["doc_id"], "Doc", active_dec["doc_title"])
        evidence.add_edge(active_dec["id"], "RECORDED_IN", active_dec["doc_id"])
    if active_dec["thread_id"]:
        evidence.add_node(active_dec["thread_id"], "Thread", active_dec["thread_channel"])
        evidence.add_edge(active_dec["id"], "DISCUSSED_IN", active_dec["thread_id"])

    # 2. Superceded lineage (up to 5 hops)
    cypher_lineage = (
        "MATCH (dec:Decision {id: $act_id})-[:SUPERSEDES*1..5]->(old_dec:Decision) "
        "OPTIONAL MATCH (p:Person)-[:AUTHORED]->(old_dec) "
        "OPTIONAL MATCH (old_dec)-[:RECORDED_IN]->(doc:Doc) "
        "OPTIONAL MATCH (old_dec)-[:DISCUSSED_IN]->(thr:Thread) "
        "RETURN old_dec.id, old_dec.title, old_dec.rationale, old_dec.decided_at, old_dec.status, "
        "p.id, p.name, doc.id, doc.title, thr.id, thr.channel"
    )
    cyphers.append(cypher_lineage)
    res_lin = g.ro_query(cypher_lineage, {"act_id": active_dec["id"]})
    lineage = []
    for lrow in res_lin.result_set or []:
        ldec = {
            "id": lrow[0],
            "title": lrow[1],
            "rationale": lrow[2],
            "decided_at": lrow[3],
            "status": lrow[4],
            "author_id": lrow[5],
            "author_name": lrow[6],
            "doc_id": lrow[7],
            "doc_title": lrow[8],
            "thread_id": lrow[9],
            "thread_channel": lrow[10],
        }
        lineage.append(ldec)
        evidence.add_node(ldec["id"], "Decision", ldec["title"])
        evidence.add_edge(active_dec["id"], "SUPERSEDES", ldec["id"])
        if ldec["author_id"]:
            evidence.add_node(ldec["author_id"], "Person", ldec["author_name"])
            evidence.add_edge(ldec["author_id"], "AUTHORED", ldec["id"])
        if ldec["doc_id"]:
            evidence.add_node(ldec["doc_id"], "Doc", ldec["doc_title"])
            evidence.add_edge(ldec["id"], "RECORDED_IN", ldec["doc_id"])

    summary = (
        f"Active decision: '{active_dec['title']}' ({active_dec['id']}). "
        f"Supersedes {len(lineage)} prior decision(s)."
    )
    return ToolResult(
        summary=summary,
        data={"active": active_dec, "lineage": lineage},
        evidence=evidence,
        cypher=cyphers,
    )


@tool(
    name="get_doc",
    description="Fetches document content by ID (runbook, ADR, or postmortem), truncated to 2000 characters.",
    params={
        "type": "object",
        "properties": {
            "doc_id": {"type": "string", "description": "Document ID"},
        },
        "required": ["doc_id"],
    },
    agents=["archivist"],
    readonly=True,
)
def get_doc(tenant: str, doc_id: str) -> ToolResult:
    g = graph_for(tenant)
    evidence = Evidence()
    cypher = (
        "MATCH (d:Doc {id: $did}) "
        "OPTIONAL MATCH (d)-[:DOCUMENTS]->(s:Service) "
        "RETURN d.id, d.title, d.kind, d.body, s.id, s.name"
    )
    res = g.ro_query(cypher, {"did": doc_id})
    rows = res.result_set or []

    if not rows:
        return ToolResult(
            summary=f"Document '{doc_id}' not found",
            data={},
            evidence=evidence,
            cypher=[cypher],
        )

    did, dtitle, dkind, dbody, sid, sname = rows[0]
    body_truncated = dbody[:2000] if dbody else ""

    evidence.add_node(did, "Doc", dtitle)
    if sid:
        evidence.add_node(sid, "Service", sname)
        evidence.add_edge(did, "DOCUMENTS", sid)

    summary = f"Doc: '{dtitle}' ({dkind})"
    return ToolResult(
        summary=summary,
        data={
            "id": did,
            "title": dtitle,
            "kind": dkind,
            "body": body_truncated,
            "service_id": sid,
            "service_name": sname,
        },
        evidence=evidence,
        cypher=[cypher],
    )
