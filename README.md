# StockPulse Store Intelligence Agent

A multi-database conversational AI agent for e-commerce store operations. Ask a natural-language question and get a grounded answer with full tool-call receipts.

## Domain and Stack

- Domain: E-commerce operations (inventory, orders, customer support, store policies)
- Backend: FastAPI, LangChain/LangGraph ReAct, Groq (`openai/gpt-oss-120b`), SentenceTransformers (`all-MiniLM-L6-v2`), Postgres + pgvector, MongoDB
- Frontend: Vite, React 18, TypeScript, Tailwind

## Architecture

```text
Browser -> React UI -> FastAPI POST /chat -> ReAct Agent
                                      |           |           |
                                   sql_query   mongo_query  handbook_search
                                      |           |           |
                                   Postgres     MongoDB      pgvector
```

The agent never connects to databases directly. Every read goes through typed tools with guardrails and structured traces.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/HLD.md](docs/HLD.md), and [docs/LLD.md](docs/LLD.md).

## Quick Start

### Prerequisites

- Python 3.12+
- `uv`
- Docker + Docker Compose
- Node.js 20+
- Groq API key

### 1. Configure environment

```bash
git clone <your-repo-url>
cd MultiDBAgent_class5_hw2_ManojKumarY
cp .env.example .env
```

Set at least:

- `GROQ_API_KEY`
- `POSTGRES_URL`
- `MONGO_URL`
- `MONGO_DB`

### 2. Start databases

```bash
docker compose up -d
docker compose ps
```

### 3. Install backend deps

```bash
uv sync
# For tests:
uv sync --extra dev
```

### 4. Seed data

```bash
uv run python scripts/seed_postgres.py
uv run python scripts/seed_mongo.py
uv run python scripts/index_policies.py
```

### 5. Start backend

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

### 6. Start frontend

```bash
cd frontend
npm install
npm run dev
```

## API Reference

### POST `/chat`

Request:

```json
{ "question": "What are the top 5 selling products this month?" }
```

Response:

```json
{
  "answer": "...",
  "tool_calls": [
    {
      "tool": "sql_query",
      "args": { "sql": "SELECT ..." },
      "result": "[...]"
    }
  ],
  "warnings": [],
  "elapsed_ms": 2341
}
```

### GET `/health`

Returns liveness:

```json
{ "status": "ok" }
```

### GET `/health/dependencies`

Returns configuration-readiness diagnostics:

```json
{
  "status": "ok",
  "checks": {
    "groq_api_key_configured": true,
    "postgres_url_configured": true,
    "mongo_url_configured": true,
    "llm_model": "openai/gpt-oss-120b",
    "embedding_model_name": "all-MiniLM-L6-v2"
  },
  "note": "Configuration presence only; POST /chat validates live connectivity."
}
```

## Recent Backend Reliability Updates

- Added clearer `/chat` failure details for provider/network errors:
  - Includes actionable hint to verify `GROQ_API_KEY`, outbound internet, and provider availability.
- Added `GET /health/dependencies` for quick startup diagnostics.
- `handbook_search` embedding model loading is lazy to avoid hard startup failures when model cache/network is unavailable.

## Frontend Refactor and UI Upgrade

`frontend/src/App.tsx` was decomposed into focused modules:

- `components/layout/AppShell.tsx`
- `pages/ChatPage.tsx`
- `hooks/useChatSession.ts`
- `components/chat/MessageList.tsx`
- `components/chat/Composer.tsx`
- `components/chat/SuggestionChips.tsx`
- `components/chat/TracePanel.tsx`

Behavior/UI improvements:

- Auto-grow composer textarea
- Enter to send, Shift+Enter newline
- Loading row with improved affordance
- Retry action on failure
- Copy actions for answer/trace blocks
- Message enter animation
- Responsive dark-theme layout polish

## Testing

### Backend

```bash
# All backend unit tests
uv run pytest tests/unit -v

# E2E (requires running backend + live dependencies)
# Optionally override target backend URL:
#   API_BASE_URL=http://localhost:8011
uv run pytest tests/e2e -v
```

### Frontend

```bash
cd frontend
npm test
npm run build
```

## Environment Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | - | Groq API key |
| `POSTGRES_URL` | Yes | - | Postgres connection string |
| `MONGO_URL` | Yes | - | Mongo connection string |
| `MONGO_DB` | Yes | `stockpulse` | Mongo database |
| `LLM_MODEL` | No | `openai/gpt-oss-120b` | Groq model |
| `EMBEDDING_MODEL_NAME` | No | `all-MiniLM-L6-v2` | SentenceTransformer model |
| `AGENT_MAX_ITERATIONS` | No | `5` | ReAct loop limit |
| `SQL_ROW_LIMIT` | No | `50` | SQL row cap |
| `SQL_TIMEOUT_MS` | No | `5000` | SQL timeout |
| `MONGO_DOC_LIMIT` | No | `20` | Mongo row cap |

## Project Structure

```text
backend/      FastAPI + agent + tools
frontend/     Vite + React UI
tests/        unit and e2e tests
scripts/      seeding and indexing
policies/     handbook source docs
docs/         architecture and design docs
SPEC.md       assignment specification
```
