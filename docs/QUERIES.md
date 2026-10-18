# Ariadne: Complete Cypher Query Catalog

This document provides a comprehensive catalog of all Cypher queries executed by Ariadne on FalkorDB, organized by subsystem.

---

## 1. Schema, Constraints & Vector Indexes

### Unique Node Constraints
```cypher
CREATE CONSTRAINT FOR (s:Service) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT FOR (c:Customer) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT FOR (p:Person) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT FOR (i:Incident) REQUIRE i.id IS UNIQUE;
CREATE CONSTRAINT FOR (d:Doc) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT FOR (f:Fact) REQUIRE f.id IS UNIQUE;
CREATE CONSTRAINT FOR (e:Episode) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT FOR (pr:Procedure) REQUIRE pr.id IS UNIQUE;
CREATE CONSTRAINT FOR (r:Run) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT FOR (t:Task) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT FOR (tc:ToolCall) REQUIRE tc.id IS UNIQUE;
CREATE CONSTRAINT FOR (act:Action) REQUIRE act.id IS UNIQUE;
CREATE CONSTRAINT FOR (ans:Answer) REQUIRE ans.id IS UNIQUE;
```

### Vector Index on Incident Nodes
```cypher
CALL db.idx.vector.createNodeIndex('Incident', 'embedding', 768, 'COSINE')
```

---

## 2. Knowledge Retrieval Queries

### Blast Radius (Downstream Dependents)
Finds all services that depend on a service up to `N` hops, along with affected customers and criticality tiers:
```cypher
MATCH (x:Service {id: $sid})
MATCH p = (s:Service)-[:DEPENDS_ON*1..4]->(x)
WITH s, min(length(p)) AS hops
OPTIONAL MATCH (c:Customer)-[:USES]->(s)
RETURN s.id AS id, s.name AS name, s.tier AS tier, hops,
       collect(DISTINCT c.name) AS customers
ORDER BY hops ASC, s.tier ASC
```

### Blast Radius (Upstream Dependencies)
Finds all upstream services that a service relies upon:
```cypher
MATCH (x:Service {id: $sid})
MATCH p = (x)-[:DEPENDS_ON*1..4]->(s:Service)
WITH s, min(length(p)) AS hops
RETURN s.id AS id, s.name AS name, s.tier AS tier, hops
ORDER BY hops ASC
```

### Service Criticality & Impact Ranking
Ranks services by customer exposure, direct dependencies, and tier level:
```cypher
MATCH (s:Service {id: $sid})
OPTIONAL MATCH (c:Customer)-[:USES]->(s)
OPTIONAL MATCH (down:Service)-[:DEPENDS_ON]->(s)
OPTIONAL MATCH (s)-[:DEPENDS_ON]->(up:Service)
RETURN s.id AS id, s.name AS name, s.tier AS tier,
       count(DISTINCT c) AS direct_customers,
       count(DISTINCT down) AS downstream_dependents,
       count(DISTINCT up) AS upstream_dependencies
```

### Architectural Choke Points
Identifies central services whose outage affects multiple Tier 0/1 systems:
```cypher
MATCH (s:Service)
MATCH (dep:Service)-[:DEPENDS_ON*1..2]->(s)
WHERE dep.tier IN [0, 1] AND s.id <> dep.id
WITH s, count(DISTINCT dep) AS tier01_dependents
WHERE tier01_dependents >= 2
OPTIONAL MATCH (c:Customer)-[:USES]->(dep2:Service)-[:DEPENDS_ON*0..2]->(s)
RETURN s.id AS id, s.name AS name, s.tier AS tier,
       tier01_dependents,
       count(DISTINCT c) AS total_customer_exposure
ORDER BY tier01_dependents DESC, total_customer_exposure DESC
```

### Dependency Shortest Path
Finds the shortest dependency graph traversal path between two services:
```cypher
MATCH (s1:Service {id: $src}), (s2:Service {id: $dst})
MATCH p = shortestPath((s1)-[:DEPENDS_ON*..8]->(s2))
RETURN [n IN nodes(p) | n.id] AS path_ids,
       [n IN nodes(p) | n.name] AS path_names,
       length(p) AS hops
```

### Expert Identification & On-Call Routing
Finds domain experts who own services or previously resolved incidents on those systems:
```cypher
MATCH (s:Service {id: $sid})
OPTIONAL MATCH (p1:Person)-[:OWNS]->(s)
OPTIONAL MATCH (p2:Person)-[:ON_CALL_FOR]->(s)
OPTIONAL MATCH (p3:Person)-[:RESOLVED]->(i:Incident)-[:AFFECTED]->(s)
RETURN s.name AS service,
       collect(DISTINCT {name: p1.name, role: 'owner', email: p1.email}) AS owners,
       collect(DISTINCT {name: p2.name, role: 'on_call', email: p2.email}) AS on_call,
       collect(DISTINCT {name: p3.name, role: 'prior_resolver'}) AS resolvers
```

---

## 3. Three-Tier Memory Layer Queries

### Tier 1: Episodic Memory Storage & Vector Recall
Storing an incident episode:
```cypher
CREATE (e:Episode {
  id: $id,
  summary: $summary,
  goal: $goal,
  outcome: $outcome,
  ts: $ts,
  embedding: $embedding
})
WITH e
MATCH (r:Run {id: $run_id})
CREATE (r)-[:CONSOLIDATED_INTO]->(e)
```

Vector similarity recall across past episodes:
```cypher
CALL db.idx.vector.queryNodes('Incident', 'embedding', 5, $query_vector)
YIELD node, score
RETURN node.id AS id, node.summary AS summary, node.root_cause AS root_cause,
       score
ORDER BY score DESC
```

### Tier 2: Bitemporal Temporal Facts
Creating a new valid fact (`valid_to = 0` indicates active current state):
```cypher
CREATE (f:Fact {
  id: $id,
  subject_id: $subject_id,
  predicate: $predicate,
  text: $text,
  valid_from: $now,
  valid_to: 0,
  confidence: $confidence
})
```

Superseding a stale fact during incident resolution (marking validity range):
```cypher
MATCH (old:Fact {subject_id: $subject_id, predicate: $predicate, valid_to: 0})
SET old.valid_to = $now
WITH old
MATCH (new:Fact {id: $new_id})
CREATE (new)-[:SUPERSEDES]->(old)
```

Querying current active truth vs. historical configuration:
```cypher
// Active current configuration truth:
MATCH (f:Fact {subject_id: $sid, valid_to: 0})
RETURN f.predicate AS property, f.text AS statement, f.valid_from AS since

// Historical evolution timeline:
MATCH (f:Fact {subject_id: $sid})
RETURN f.predicate AS property, f.text AS statement,
       f.valid_from AS from, f.valid_to AS to,
       CASE WHEN f.valid_to = 0 THEN 'CURRENT' ELSE 'SUPERSEDED' END AS status
ORDER BY f.valid_from DESC
```

### Tier 3: Procedural Memory (Runbooks & SOPs)
Retrieving matching procedure by trigger keyword/pattern:
```cypher
MATCH (p:Procedure)
WHERE toLower($text) CONTAINS toLower(p.trigger_text)
RETURN p.id AS id, p.name AS name, p.steps AS steps,
       p.success_count AS success_count, p.fail_count AS fail_count
ORDER BY p.success_count DESC
LIMIT 3
```

Reinforcing procedure success counter upon verified resolution:
```cypher
MATCH (p:Procedure {id: $pid})
SET p.success_count = p.success_count + 1,
    p.last_used = $now
RETURN p.name, p.success_count
```

---

## 4. Multi-Agent Coordination Substrate Queries

### Run Initialization & Task Registration
```cypher
CREATE (r:Run {
  id: $run_id,
  mode: $mode,
  mission: $mission,
  status: 'running',
  started_at: $now,
  completed_at: 0
})
```

Registering tasks under the Run:
```cypher
MATCH (r:Run {id: $run_id})
CREATE (t:Task {
  id: $tid,
  run_id: $run_id,
  kind: $kind,
  status: 'open',
  owner: '',
  payload: $payload,
  result: '',
  created_at: $now,
  claimed_at: 0,
  done_at: 0
})
CREATE (r)-[:HAS_TASK]->(t)
```

### Atomic CAS Task Claim (Single-Statement Conditional SET)
The core zero-duplicate coordination primitive:
```cypher
MATCH (t:Task {id: $tid, status: 'open'})
SET t.status = 'claimed',
    t.owner = $worker_id,
    t.claimed_at = timestamp()
RETURN t.id
```
*Guarantees: If two workers attempt to claim the same task concurrently, exactly one succeeds and returns `t.id`; the other returns empty results.*

### Task Completion & Handoff Next Edges
```cypher
MATCH (t:Task {id: $tid})
SET t.status = 'done',
    t.result = $result,
    t.done_at = timestamp()
```

Creating `[:NEXT]` DAG handoff edges:
```cypher
MATCH (t1:Task {id: $src}), (t2:Task {id: $dst})
CREATE (t1)-[:NEXT {note: $note, ts: timestamp()}]->(t2)
```

---

## 5. Provenance & Audit Graph Queries

### Recording Tool Calls and Grounded Evidence
```cypher
MATCH (t:Task {id: $tid})
CREATE (tc:ToolCall {
  id: $tcid,
  tool: $tool_name,
  args: $args_json,
  duration_ms: $duration,
  status: 'ok',
  ts: timestamp()
})
CREATE (t)-[:INVOKED]->(tc)
WITH tc
UNWIND $evidence_ids AS eid
MATCH (e {id: eid})
CREATE (tc)-[:PRODUCED_EVIDENCE]->(e)
```

### Synthesized Answer Lineage
```cypher
MATCH (r:Run {id: $run_id})
CREATE (ans:Answer {
  id: $ans_id,
  text: $answer_text,
  citations: $citation_ids,
  ungrounded: $ungrounded_ids,
  created_at: timestamp()
})
CREATE (r)-[:ANSWERED]->(ans)
WITH ans
UNWIND $citation_ids AS cid
MATCH (n {id: cid})
CREATE (ans)-[:CITES]->(n)
```
