# StockPulse Store Intelligence Agent

> A multi-database conversational AI agent for e-commerce store operations. Ask a natural-language question — get a grounded answer with full tool-call receipts.

**Domain:** E-commerce operations (inventory, orders, customer support, store policies)  
**Stack:** FastAPI · LangChain v1 ReAct · OpenAI GPT-4o-mini · Supabase Postgres + pgvector · MongoDB Atlas · Vite + React + TypeScript

---

## Architecture

```
Browser → React UI → FastAPI POST /chat → LangChain ReAct Agent
                                              ↓            ↓            ↓
                                        sql_query   mongo_query  handbook_search
                                              ↓            ↓            ↓
                                         Postgres      MongoDB      pgvector
```

The agent **never** connects to a database directly. Every read goes through one of the three typed, sandboxed tools. Tools always return strings — the ReAct loop never crashes on a database exception.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for full C4 diagrams.

---

## Quick Start

### Prerequisites

- Python 3.12+, `uv` package manager
- Docker & Docker Compose
- Node.js 20+ (for the frontend)
- An OpenAI API key

### 1. Clone & configure environment

```bash
git clone <your-repo-url>
cd MultiDBAgent_class5_hw2_ManojKumarY

cp .env.example .env
# Edit .env and fill in your keys:
#   OPENAI_API_KEY=sk-...
#   POSTGRES_URL=postgresql://stockpulse:stockpulse_dev@localhost:5432/stockpulse
#   MONGO_URL=mongodb://stockpulse:stockpulse_dev@localhost:27017/stockpulse?authSource=admin
#   MONGO_DB=stockpulse
```

### 2. Start the databases

```bash
docker compose up -d
# Wait for healthchecks to pass (~10 seconds)
docker compose ps
```

### 3. Install Python dependencies

```bash
uv sync
```

### 4. Seed the databases

```bash
# Postgres — products, customers, orders
uv run python scripts/seed_postgres.py

# MongoDB — reviews, support_tickets, activity_logs
uv run python scripts/seed_mongo.py

# pgvector — chunk and embed the policy documents
uv run python scripts/index_policies.py
```

### 5. Start the backend

```bash
uv run uvicorn backend.main:app --reload --port 8000
# API docs available at http://localhost:8000/docs
```

### 6. Start the frontend

```bash
cd frontend
npm install
npm run dev
# App available at http://localhost:5173
```

---

## API Reference

### `POST /chat`

```json
// Request
{ "question": "What are the top 5 selling products this month?" }

// Response
{
  "answer": "The top 5 selling products this month are...",
  "tool_calls": [
    {
      "tool": "sql_query",
      "args": { "sql": "SELECT p.name, SUM(o.quantity) AS total_sold ..." },
      "result": "[{\"name\": \"Wireless Mouse\", \"total_sold\": 21}]"
    }
  ],
  "warnings": [],
  "elapsed_ms": 2341
}
```

---

## Running Tests

```bash
# Unit tests only (no live databases needed)
uv run pytest tests/unit/ -v

# All tests (requires live Postgres + Mongo)
uv run pytest -v

# With coverage report
uv run pytest --cov=backend --cov-report=term-missing
```

---

## Why I Chose X

### Domain: E-commerce Operations
Airlines have been done in class. E-commerce gives a natural three-way split: transactional data (Postgres), customer sentiment (MongoDB), and policy documents (RAG). Every store manager can immediately relate to the demo questions.

### Model: GPT-4o-mini (default)
Fast, cheap, and accurate enough for tool-calling at temperature=0. If routing accuracy falls below acceptable in testing, the model can be swapped to `gpt-4o` by changing `LLM_MODEL` in `.env` — no code change required.

### Postgres + pgvector (not a separate vector DB)
For this scale (< 100 policy chunks), running pgvector as an extension on the same Supabase Postgres instance eliminates an entire third cloud dependency. The `policy_chunks` table lives alongside `products` and `orders`. One connection pool, one backup policy, one set of credentials.

### MongoDB for Operational Data
Reviews, support tickets, and activity logs are naturally document-shaped — variable fields, nested comments, free-text issues. MongoDB's `find()` with a filter dict maps cleanly to how a store manager thinks ("show me open tickets about delayed shipments").

---

## What Broke and How I Fixed It

### 1. The ReAct loop crashing on database exceptions
**Problem:** When Postgres was unreachable, `psycopg2.OperationalError` propagated up through LangChain and crashed the entire `agent_executor.invoke()` call.

**Fix:** Wrapped every database call in `try/except` inside the tool function. Tools now always return a descriptive string (e.g., `"SQL ERROR: could not connect to server"`). LangChain reads this as an Observation and the agent responds honestly: "I was unable to retrieve the data due to a connection error."

### 2. LIMIT injection breaking aggregate queries
**Problem:** Auto-injecting `LIMIT 50` broke queries like `SELECT COUNT(*) FROM orders GROUP BY status` because the appended LIMIT confused the query planner.

**Fix:** The `_inject_limit()` function now checks for `GROUP BY`, `HAVING`, `COUNT(`, `SUM(`, `AVG(`, `MAX(`, `MIN(` before injecting. Aggregate queries are left untouched.

### 3. pgvector similarity threshold returning noise
**Problem:** Asking "What were our sales in 1990?" (the failure case) also triggered the RAG tool returning distant policy chunks, causing the agent to hallucinate policy content.

**Fix:** Added a `rag_similarity_threshold` (default 0.2). Results below this cosine similarity score are filtered out and return `[]`. The agent then correctly reports "no relevant policy found".

---

## What I Would Change With Another Week

1. **Cache embeddings for repeat queries.** I noticed the agent embeds the same RAG query twice per session (once during reasoning, once during the answer synthesis). Adding a simple LRU cache keyed on the query string would halve the OpenAI embedding cost and latency for repeat questions.

2. **Add a fourth tool: `order_status_lookup`.** A dedicated tool that takes an `order_id` and returns its full lifecycle (created → shipped → delivered) would handle the most common support ticket pattern — "where is my order?" — without the agent needing to write a multi-join SQL query.

3. **Stream the agent's reasoning to the UI.** Currently the frontend shows a spinner for 3–8 seconds. With LangChain's streaming callbacks and Server-Sent Events, the UI could show each Thought/Action/Observation as it happens, making the agent feel dramatically faster.

4. **Eval harness with regression tracking.** Run the 5 acceptance questions on every commit and store the results in a JSON file. Alert if any question routes to the wrong tool across two consecutive runs.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ | — | OpenAI API key |
| `POSTGRES_URL` | ✅ | — | Full Postgres connection string |
| `MONGO_URL` | ✅ | — | MongoDB connection string |
| `MONGO_DB` | ✅ | `stockpulse` | MongoDB database name |
| `LLM_MODEL` | ❌ | `gpt-4o-mini` | LangChain LLM model name |
| `AGENT_MAX_ITERATIONS` | ❌ | `5` | Max ReAct loop iterations |
| `SQL_ROW_LIMIT` | ❌ | `50` | Auto-injected LIMIT |
| `SQL_TIMEOUT_MS` | ❌ | `5000` | Postgres statement timeout |
| `MONGO_DOC_LIMIT` | ❌ | `20` | Hard cap on Mongo results |

---

## Project Structure

```
├── backend/          # FastAPI + LangChain backend
│   ├── config.py     # Pydantic settings
│   ├── main.py       # FastAPI app + /chat endpoint
│   ├── agent.py      # ReAct agent factory + system prompt
│   └── tools/        # sql_tool, mongo_tool, rag_tool
├── scripts/          # Database seed + indexing scripts
├── policies/         # Markdown policy documents (RAG source)
├── frontend/         # Vite + React + TypeScript chat UI
├── tests/            # pytest unit, integration, e2e
├── docs/             # ARCHITECTURE.md, HLD.md, LLD.md
├── docker-compose.yml
├── pyproject.toml
└── SPEC.md
```

---

## Deliverables

- [x] SPEC.md (committed first)
- [x] Working backend (FastAPI + LangChain v1 + 3 tools)
- [x] Working frontend (chat UI with tool-call trace)
- [x] Seed data and load scripts for all three stores
- [x] Unit tests per tool + e2e tests
- [x] `.env.example` (no secrets)
- [x] README with setup, architecture, decisions, findings
