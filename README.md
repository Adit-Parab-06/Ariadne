# Ariadne: Graph-Native Multi-Agent Incident Response & Institutional Memory

> **Built for GraphHacks 2026** • Powered by **FalkorDB** + **Google Gemini** + **FastAPI** + **React 18 / Tailwind v3**

Ariadne is an enterprise multi-agent "company brain" where **FalkorDB is load-bearing** across all four operational dimensions:
1. **Knowledge Substrate**: Multi-hop graph traversals for blast radius, bottleneck choke points, service criticality, and domain expert discovery.
2. **Coordination Substrate**: Zero-duplicate atomic CAS task dispatching and `[:NEXT]` DAG handoffs directly in the graph—replacing Redis, Celery, and Kafka.
3. **Institutional Memory**: Three-tier memory layer combining **Episodic Memory** (incident postmortems with Cosine vector search), **Temporal Facts** (bitemporal `valid_from` / `valid_to=0` configuration truth), and **Procedural Memory** (learned standard operating procedures).
4. **Audit Provenance**: Cryptographic lineage tracing every synthesized answer back to underlying tool calls and evidence graph nodes (`Run ➔ Task ➔ ToolCall ➔ Evidence ➔ Answer`).

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │           FastAPI Gateway            │
                      │   REST + SSE Streaming + FastMCP     │
                      └──────────────────┬───────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │       Multi-Agent Orchestration Bus           │
                 └───────┬───────────────┬───────────────┬───────┘
                         │               │               │
                 ┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
                 │    Scout     │ │  Archivist  │ │  Responder  │
                 │ (Topology &  │ │ (Vector &   │ │ (Human-in-  │
                 │ Blast Radius)│ │ Memory SOP) │ │ the-Loop)   │
                 └───────┬──────┘ └──────┬──────┘ └──────┬──────┘
                         │               │               │
                         └───────────────┼───────────────┘
                                         │ [:NEXT] DAG
                                 ┌───────▼──────┐
                                 │ Synthesizer  │
                                 │  (Grounded   │
                                 │  Citations)  │
                                 └───────┬──────┘
                                         │
                     ┌───────────────────┴───────────────────┐
                     │          FalkorDB Substrate           │
                     │  Graph + Vector Index + Atomic CAS    │
                     └───────────────────────────────────────┘
```

---

## Key Innovations

### 1. Zero-Duplicate Coordination (No Redis/Celery/Kafka)
Instead of distributed lock managers (Redlock, Zookeeper) or external task brokers, Ariadne coordinates concurrent agents via **single-statement conditional Cypher CAS**:
```cypher
MATCH (t:Task {id: $tid, status: 'open'})
SET t.status = 'claimed', t.owner = $worker, t.claimed_at = timestamp()
RETURN t.id
```
**Stress Benchmark**: In our test suite, **200 contending tasks** claimed across **8 parallel worker threads** alongside 93 concurrent graph reads completed in **0.577s** with **0 duplicate claims** (346.4 tasks/second).

### 2. Bitemporal Memory (Eliminating Stale Knowledge Hallucinations)
Traditional vector databases append conflicting configurations when infrastructure changes. Ariadne models facts with bitemporal validity:
- Active truth has `valid_to = 0`.
- When an incident resolution updates a parameter, the existing fact's `valid_to` is set to the current timestamp and linked via `[:SUPERSEDES]`.
- Retrieval queries filter strictly on `valid_to = 0`, permanently preventing LLM contradictions.

### 3. Strict Anti-Hallucination & Provenance Grounding
Every entity cited in the synthesizer's answer (`[[node_id]]`) is checked against the accumulated evidence subgraph. Ungrounded citations are scrubbed, ensuring 100% deterministic traceability.

### 4. Apple-Style Design System & Interactive 2D Canvas
- Cupertino spring animations, 20px card radii, and light/dark theme semantic variables.
- Interactive `react-force-graph-2d` canvas: clicking citations (`[[svc_payments_api]]`) centers and zooms the canvas directly onto that entity.
- Real-time SSE streaming for parallel agent lanes, tool executions, and handoffs.

---

## Multi-Tenant Support

Ariadne ships pre-seeded with two isolated enterprise tenants:
- **Northwind Cloud**: FinTech payments infrastructure (`payments-api`, `ledger-db`, `checkout-api`, customer bank integrations).
- **Acme Corp**: Global logistics and eCommerce infrastructure (`order-service`, `inventory-db`, `warehouse-api`, shipping tracking).

---

## Quickstart Guide

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 20+

### 2. Environment Setup
```bash
# Clone and enter repository
cd Ariadne

# Create Python virtual environment
python -m venv .venv

# Activate environment:
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Configure environment
cp .env.example .env
# Open .env and add your GEMINI_API_KEY
```

### 3. Start FalkorDB
```bash
docker compose up -d falkordb
```

### 4. Seed Knowledge Graphs
```bash
python -m backend.app.seed
```
*Seeds both `northwind` and `acme` with services, dependencies, customers, incidents, procedures, and vector embeddings in ~2 seconds.*

### 5. Launch Backend Server
```bash
# In your activated virtualenv:
uvicorn app.api.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```
- API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 6. Launch Frontend App
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Model Context Protocol (FastMCP)

Ariadne exposes all 11 readonly knowledge tools as a standard **Model Context Protocol (MCP)** server for IDEs like Cursor, Claude Desktop, and Antigravity:

### Run MCP Server via stdio
```bash
python backend/app/mcp_server.py --transport stdio
```

### Run MCP Probe Test
```bash
python scripts/mcp_probe.py
```
*Discovers all 11 tools and tests blast radius calculation over stdio.*

---

## Test Suite Execution

Run the complete test suite across all subsystems:
```bash
pytest backend/tests -v
```
**Coverage**:
- `test_seed.py`: Dual-tenant schema, constraints, and seed data integrity.
- `test_knowledge.py`: Graph retrieval tools (blast radius, choke points, paths, experts).
- `test_memory.py`: Three-tier memory layer (facts, episodes, procedures).
- `test_coordination.py`: Atomic CAS task claiming and concurrency benchmarks.
- `test_orchestrator.py`: Multi-agent pipeline, handoffs, and citation grounding.
- `test_api.py`: FastAPI endpoints, SSE event streaming, action approval, and resolution.

---

## Documentation

- [`docs/QUERIES.md`](docs/QUERIES.md): Complete Cypher query reference manual.
- [`docs/DEFENSE.md`](docs/DEFENSE.md): Architectural defense and technical rationale for evaluators.
- [`docs/PROBE_RESULTS.md`](docs/PROBE_RESULTS.md): Benchmark results, MCP probe verification, and system metrics.

---

## License

Built for GraphHacks 2026. MIT License.
