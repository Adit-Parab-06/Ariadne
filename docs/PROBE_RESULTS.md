# Ariadne: Phase 0 Probe Results

Date: October 17, 2026
Verified Environment: Python 3.14, Docker 29.8.0, FalkorDB (latest), google-genai 2.31.0

---

## 1. FalkorDB Probes (`scripts/smoke_falkordb.py`)

All 9 checks **PASSED**.

### Key Findings & Corrections

#### A. `shortestPath` Syntax Requirement (CORRECTION)
- **Finding**: Running `MATCH p = shortestPath(...)` causes:
  `FalkorDB currently only supports shortestPaths in WITH or RETURN clauses`
- **Working Syntax**:
  ```cypher
  MATCH (a:Service {id: $from_id}), (b:Service {id: $to_id})
  WITH shortestPath((a)-[:DEPENDS_ON*]->(b)) AS p
  RETURN length(p), [n IN nodes(p) | n.id] AS ids
  ```
- **Correction Applied**: All downstream queries in Phase 2+ must bind `shortestPath` inside a `WITH` or `RETURN` clause.

#### B. Vector Score Semantics: DISTANCE (Smaller = Closer)
- Probe query against 4D test vectors with target `[1, 0, 0, 0]`:
  * Exact match `v1` (`[1, 0, 0, 0]`): **Score = 0.0**
  * Diagonal vector `v3` (`[0.7071, 0.7071, 0, 0]`): **Score = 0.292893**
  * Orthogonal vector `v2` (`[0, 1, 0, 0]`): **Score = 1.0**
- **Conclusion**: FalkorDB's cosine vector index returns **cosine distance** ($1 - \text{cosine similarity}$).
- **Formula for downstream ranker**:
  $$\text{similarity} = 1.0 - \text{score}$$
  (Or sort ascending by `score` where smaller is ranked higher).

#### C. `LIMIT $k` with Parameters
- Parameterized `LIMIT $k` is fully supported:
  ```cypher
  MATCH (s:Service) RETURN s.id ORDER BY s.id LIMIT $k
  ```
  Verified with `params={'k': 2}`.

#### D. Conditional SET Atomic Compare-and-Swap (CAS)
- Query:
  ```cypher
  MATCH (t:Task {id: $id}) WHERE t.status = 'open'
  SET t.status = 'claimed'
  RETURN t.id
  ```
- First execution returned `[['task_claim_test']]`.
- Second execution returned `[]` (0 rows).
- **Conclusion**: Single-statement Cypher conditional updates provide true atomic task claims.

#### E. Native Graph Algorithms
- `CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score`: **PASS**
- `CALL algo.betweenness({nodeLabels: ['Service'], relationshipTypes: ['DEPENDS_ON']}) YIELD node, score`: **PASS**

---

## 2. Gemini 3.8 Flash Probes (`scripts/smoke_gemini.py`)

All 5 checks **PASSED**.

### Key Findings & Call Shapes

#### A. Thinking Levels
- `thinking_level: 'low'` works reliably for tool execution and plain generation.
- `thinking_level: 'minimal'` raises `BadRequestError: 400` as expected.
- **Rule**: All agent calls and synthesis calls must specify `generation_config={'thinking_level': 'low'}`.

#### B. Tool-Call Loop & Turn Continuation
- Working call shape for returning tool results:
  ```python
  it2 = client.interactions.create(
      model=settings.GEMINI_MODEL,
      previous_interaction_id=it.id,
      tools=tools,
      generation_config={"thinking_level": "low"},
      input=[{
          "type": "function_result",
          "name": fc_step.name,
          "call_id": fc_step.id,
          "result": [{"type": "text", "text": json.dumps(payload)}]
      }]
  )
  ```

#### C. Parallel Function Calls
- Gemini can emit multiple function calls in a single turn (`it.steps` contains multiple `function_call` steps).
- Passing all results in a single `input` array containing multiple `function_result` dictionaries is verified and supported.

#### D. Embeddings (`gemini-embedding-001`)
- Call shape:
  ```python
  from google.genai import types

  resp = client.models.embed_content(
      model="gemini-embedding-001",
      contents=text,
      config=types.EmbedContentConfig(
          output_dimensionality=768,
          task_type="RETRIEVAL_DOCUMENT"
      )
  )
  ```
- **L2 Normalization**:
  * Raw vector length: **768**
  * Raw L2 norm: **0.591249**
  * Normalized L2 norm: **1.000000**
- **Rule**: All 768-d vectors must be L2-normalized in Python before storing into FalkorDB vector indexes.

---

## 3. MCP SDK Probes (`scripts/mcp_probe.py`)

All checks **PASSED**.

### Key Findings & Corrections

#### A. FastMCP in MCP 2.x
- **Finding**: In `mcp 2.3.0`, importing `from mcp.server.fastmcp import FastMCP` raises `ModuleNotFoundError`.
- **Working Import**:
  ```python
  from mcp.server.mcpserver import MCPServer
  ```
- **Server Initialization**:
  ```python
  server = MCPServer("ariadne")
  ```

#### B. Tool Registration API
- Uses decorator `@server.tool(name=..., description=...)`:
  ```python
  @server.tool(name="blast_radius", description="...")
  def blast_radius(service_id: str, direction: str = "dependents", max_hops: int = 4, tenant: str = "northwind") -> str:
      ...
  ```
- Exposes all 11 readonly tools from the Ariadne registry.

#### C. Transports
- Running over stdio:
  `server.run(transport="stdio")`
- Running over streamable HTTP:
  `server.run(transport="streamable-http", host=host, port=port)`

#### D. Verified Stdio Client Execution
- `scripts/mcp_probe.py` connected to `app.mcp_server` over stdio via `StdioServerParameters`, successfully listed 11 tools, and executed `blast_radius` on `svc_payments_api` returning real graph results and Cypher query strings.

---

## Summary of Acceptance Gate Status

| Check | Expected | Actual Result | Status |
| :--- | :--- | :--- | :--- |
| FalkorDB Docker Service | Running on 6379 & 3000 | Container `ariadne-falkordb-1` Up | **PASS** |
| FalkorDB Smoke Tests | All PASS | All 9 checks PASSED | **PASS** |
| Gemini Smoke Tests | All PASS | All 5 checks PASSED | **PASS** |
| MCP SDK Probe | 11 tools, blast_radius over stdio | 11 tools, real dependents returned | **PASS** |
| `docs/PROBE_RESULTS.md` | Recorded on disk | Saved with all corrections | **PASS** |


---

## 3. End-to-End System Benchmark & Acceptance Results (Phase 11 Verification)

### A. FalkorDB Atomic CAS Concurrency Benchmark
- **Command**: `python -c "from app.coordination.lab import run_concurrency_lab; ..."`
- **Northwind FinTech Cluster (200 tasks, 8 threads, 2 concurrent readers)**:
  ```json
  {
    "run_id": "run_2a8c8387",
    "claimed": 200,
    "unique_claimed": 200,
    "duplicates": 0,
    "total_in_graph": 200,
    "done_in_graph": 200,
    "seconds": 0.577,
    "throughput": 346.4,
    "concurrent_reads": 93
  }
  ```
- **Acme Logistics Cluster (100 tasks, 4 threads)**:
  ```json
  {
    "run_id": "run_a0168179",
    "claimed": 100,
    "unique_claimed": 100,
    "duplicates": 0,
    "total_in_graph": 100,
    "done_in_graph": 100,
    "seconds": 0.221,
    "throughput": 453.4,
    "concurrent_reads": 49
  }
  ```
- **Outcome**: **0 duplicate task claims across all benchmark runs**. Zero distributed locks required.

---

### B. FastMCP Server & Protocol Verification (`scripts/mcp_probe.py`)
- **Transport**: `stdio` and `streamable-http`
- **Total Tools Discovered**: 11 (all readonly knowledge tools)
  - `resolve_service`, `blast_radius`, `service_criticality`, `choke_points`, `dependency_path`, `find_experts`, `customer_history`, `trace_decision`, `get_doc`, `recall_memory`, `similar_incidents`
- **Live Blast Radius Execution over stdio**:
  - Target: `svc_payments_api`
  - Dependents found: 2 (`checkout-api`, `checkout-web`) with customer impacts (`Pinecrest Bank`, `Helios Retail`, `Orbit Pay`).
- **Outcome**: **100% PASS**.

---

### C. Backend Test Suite Verification (`pytest backend/tests -q`)
- **Total Tests Executed**: 30
- **Total Tests Passed**: 30 (100%)
- **Duration**: 6.04s
- **Breakdown**:
  - `test_seed.py`: Dual-tenant schema, constraints, entity loader integrity.
  - `test_knowledge.py`: Graph retrieval tools (blast radius, choke points, paths, experts).
  - `test_memory.py`: Three-tier memory layer (facts bitemporal validity, episodes, procedures).
  - `test_coordination.py`: Atomic CAS task claiming and concurrency benchmarks.
  - `test_orchestrator.py`: Multi-agent pipeline, handoffs, and citation grounding.
  - `test_api.py`: FastAPI endpoints, SSE event streaming, action approval, and resolution.

---

### D. Frontend Production Build Verification (`npm run build`)
- **Modules Transformed**: 3,004
- **TypeScript Typecheck**: 0 errors
- **Production Chunks**:
  - `dist/index.html` (0.89 kB)
  - `dist/assets/index-DlsBCrMM.css` (23.51 kB)
  - `dist/assets/index-CijmF36O.js` (534.88 kB)
- **Outcome**: **100% Clean Bundle**.
