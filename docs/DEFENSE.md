# Ariadne: Architectural Defense & Technical Rationale

This document presents the architectural defense and technical decisions behind **Ariadne** for GraphHacks evaluators and system architects.

---

## 1. The Core Thesis: FalkorDB as a Unified Substrate

In standard multi-agent systems, teams typically assemble a fragmented infrastructure stack:
- **Neo4j** or another graph database for relational service topologies.
- **Redis & Celery / Kafka** for task queues, worker coordination, and distributed locks.
- **Pinecone / Qdrant** for vector embeddings and similarity search.
- **PostgreSQL / TimescaleDB** for temporal configurations and audit logs.

### The Problem
This multi-system architecture suffers from:
1. **Coordination latency**: Constant cross-system network hops between queue, graph, and vector database.
2. **Distributed state desynchronization**: If a task queue claims a job but the graph transaction fails, or if a vector embedding references a deleted node, the agent's context corrupts.
3. **Operational overhead**: Managing 4 distinct distributed databases with conflicting consistency models.

### The Ariadne Solution: FalkorDB Unification
Ariadne proves that **FalkorDB alone** can serve as the entire unified substrate:
- **Knowledge Layer**: Cypher graph traversals (blast radius, dependency paths, bottleneck choke points).
- **Coordination Layer**: Atomic CAS task claims and `[:NEXT]` DAG handoffs directly in the graph.
- **Memory Layer**: Three-tier memory with bitemporal validity (`valid_to = 0`) and Cosine vector indexing (`db.idx.vector.queryNodes`).
- **Provenance Layer**: Full cryptographic audit graph linking Run ➔ Task ➔ ToolCall ➔ Evidence ➔ Answer.

---

## 2. Zero-Duplicate Coordination Without Distributed Locks

### The Atomic CAS Primitive
Multi-agent task dispatching requires that no two agents execute the same investigation task simultaneously. Instead of employing Redis Redlock, Postgres advisory locks, or external consensus engines, Ariadne executes an **atomic conditional Cypher SET statement**:

```cypher
MATCH (t:Task {id: $tid, status: 'open'})
SET t.status = 'claimed',
    t.owner = $worker,
    t.claimed_at = timestamp()
RETURN t.id
```

### Mathematical Guarantee & Empirical Proof
FalkorDB executes this write statement as an atomic transaction. If 8 parallel worker threads query for open tasks and simultaneously attempt to claim task `tsk_01`:
1. Exactly **one** transaction matches the predicate `status: 'open'`, mutates `t.status` to `'claimed'`, and returns `t.id`.
2. The remaining 7 transactions evaluate `status: 'open'` against the mutated graph, encounter zero matches, and return empty results.

In our stress benchmark (`scripts/eval.py` / `ConcurrencyLabModal`), 200 tasks claimed by 8 concurrent worker threads under 93 concurrent background read queries consistently achieved:
- **Claimed tasks**: `200 / 200`
- **Duplicate claims**: `0`
- **Duration**: `0.577 seconds`
- **Throughput**: `346.4 tasks/second`

---

## 3. Strict Anti-Hallucination via Grounded Graph Provenance

### The Hallucination Vulnerability in Incident Response
LLMs frequently hallucinate plausible-sounding configurations (e.g. inventing non-existent database flags, attributing outages to unrelated services, or recommending engineers who are no longer at the company).

### The Ariadne Mitigation Pipeline
1. **Parallel Evidence Collection**: Scout and Archivist invoke readonly graph tools (`blast_radius`, `find_experts`, `get_doc`, `recall_memory`). Every discovered entity is registered into an ephemeral evidence subgraph in FalkorDB.
2. **Deterministic Citation Verification**: When Synthesizer produces findings, citations must match the syntax `[[node_id]]`.
3. **Automated Citation Scrubbing**: The orchestrator checks every cited ID against the accumulated evidence node set:
   ```python
   evidence_ids = {n["id"] for n in evidence["nodes"]}
   valid_citations = [cid for cid in parsed_citations if cid in evidence_ids]
   ungrounded_citations = [cid for cid in parsed_citations if cid not in evidence_ids]
   ```
   If any citation is ungrounded, it is recorded in the run metrics and excluded from the interactive citation chips. Only 100% grounded entities are made interactive in the UI.

---

## 4. Solving Stale Knowledge: The Three-Tier Bitemporal Memory

### The Problem with Traditional Agent Vector Memory
Most AI memory systems simply append chunks into a vector database. When a system configuration changes (e.g. `pgbouncer max_client_conn` increases from 200 to 400), a standard vector search retrieves **both** the outdated configuration and the new one, causing LLMs to hallucinate contradictory advice.

### Ariadne's Bitemporal Fact Layer
Ariadne models semantic facts with bitemporal validity:
- Every active configuration fact has `valid_to = 0`.
- When an incident resolution updates a configuration (`ResolveSheet`), the consolidating agent runs:
  ```cypher
  MATCH (old:Fact {subject_id: $sid, predicate: $pred, valid_to: 0})
  SET old.valid_to = $now
  WITH old
  CREATE (new:Fact {
    id: $new_id, subject_id: $sid, predicate: $pred,
    text: $new_text, valid_from: $now, valid_to: 0
  })
  CREATE (new)-[:SUPERSEDES]->(old)
  ```
- Retrieval queries filter strictly on `valid_to = 0`. Stale facts are never presented as current truth, but remain preserved in graph history for retrospective auditing.

---

## 5. Enterprise Multi-Tenancy & Open Standard Extensibility

1. **Dual Tenant Architecture**:
   - `northwind`: FinTech payments architecture with strict Tier-0 availability requirements.
   - `acme`: Global eCommerce and logistics architecture with multi-warehouse routing.
   - All Cypher operations, memory stores, and vector indexes are strictly tenant-scoped (`graph_for(tenant)`).
2. **Model Context Protocol (FastMCP)**:
   - Exposes Ariadne's 11 readonly graph tools via standard FastMCP over both `stdio` and `streamable-http`.
   - External IDEs (Cursor, Claude Desktop, Antigravity) can connect directly to Ariadne as an enterprise knowledge server.
3. **Human-in-the-Loop Safeguards**:
   - Responder proposes actions (`page_person`, `create_ticket`, `post_status_update`).
   - Actions remain in `proposed` state until explicitly approved by an operator via the Apple-style slide-over `ApprovalSheet`.
