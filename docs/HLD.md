# High-Level Design (HLD) — StockPulse Agent

> Maps SPEC.md requirements to system components. For implementation-level
> contracts see [LLD.md](./LLD.md). For C4 diagrams see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## 1. System Goals (from SPEC.md §1)

1. **Unified query interface** — one question, one answer, with receipts.
2. **Deterministic tool routing** — SQL for transactions, MongoDB for sentiment, RAG for policies.
3. **Traceable answers** — every response includes `tool_calls`, `warnings`, `elapsed_ms`.
4. **Fail-safe agent loop** — tools never crash the ReAct loop; errors are reported as strings.

---

## 2. Runtime Architecture

```
Browser (React/Vite :5173)
    │  POST /chat {"question": "..."}
    ▼
FastAPI (Uvicorn :8000)
    │  main.py → validate request, start timer
    ▼
ReAct Agent (langgraph.prebuilt.create_react_agent + ChatGroq)
    │  agent.py → system prompt from SPEC.md §3
    │  Calls tools in a loop until no more tool_calls
    ▼
Tool Layer (backend/tools/)
    ├── sql_query   → Postgres (psycopg2, read-only, LIMIT 50, 5s timeout)
    ├── mongo_query  → MongoDB  (pymongo, whitelist, cap 20, no $where)
    └── handbook_search → pgvector (SentenceTransformer embed + cosine search)
```

**Key constraint:** the agent never holds a database connection. Every data access
goes through a typed, sandboxed `@tool` function that returns a string.

---

## 3. Backend Module Layout

### 3.1 Configuration (`backend/config.py`)
- `pydantic_settings.BaseSettings` loading from `.env`.
- Required: `GROQ_API_KEY`, `POSTGRES_URL`, `MONGO_URL`.
- Defaults: `LLM_MODEL=openai/gpt-oss-120b`, `EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2`,
  `EMBEDDING_DIM=384`, `AGENT_MAX_ITERATIONS=5`.

### 3.2 API Layer (`backend/main.py`)
- FastAPI app with two routes: `POST /chat` and `GET /health`.
- Pydantic models: `ChatRequest`, `ToolCallRecord`, `ChatResponse`.
- Message parser: `_extract_tool_calls()` walks LangGraph's `messages` list,
  matching `AIMessage.tool_calls` to `ToolMessage.content` by `tool_call_id`.
- Answer extractor: `_get_final_answer()` finds the last `AIMessage` without
  `tool_calls` — the agent's final grounded answer.
- CORS: allows `http://localhost:5173` (Vite dev server) per SPEC.md §5.

### 3.3 Agent Layer (`backend/agent.py`)
- Builds `langgraph.prebuilt.create_react_agent` with `ChatGroq` + system prompt.
- System prompt is the exact text from SPEC.md §3 (routing rules + hard rules).
- `recursion_limit` set via `agent_max_iterations * 2 + 2` on invoke (per SPEC.md §5 max_iterations=5).
- Module-level singleton: `agent = build_agent()`, imported once by `main.py`.

### 3.4 Tool Layer (`backend/tools/`)
- `sql_tool.py`: read-only SQL with 11 forbidden keywords, multi-statement check,
  auto-LIMIT 50 (skipped for aggregates), 5s `statement_timeout`.
- `mongo_tool.py`: collection whitelist (`reviews`, `support_tickets`, `activity_logs`),
  recursive filter safety check (`$where`, `$function`, `$accumulator`), hard cap 20.
- `rag_tool.py`: local `SentenceTransformer` singleton (384-dim), pgvector cosine
  similarity search on `policy_chunks` table, similarity threshold 0.2, max k=5.

---

## 4. API Contract (from SPEC.md §5)

### POST `/chat`
Request:
```json
{ "question": "Which customers have placed the most orders?" }
```

Response:
```json
{
  "answer": "...",
  "tool_calls": [
    {"tool": "sql_query", "args": {"sql": "..."}, "result": "[...]"}
  ],
  "warnings": [],
  "elapsed_ms": 2310
}
```

### GET `/health`
```json
{ "status": "ok" }
```

### Error Responses
| Status | When |
|--------|------|
| `422` | Missing or malformed `question` field |
| `500` | Unrecoverable agent error — returns `{"detail": "Agent error: ..."}` |

---

## 5. Error and Warning Semantics

- Tool-level failures are returned as strings: `SQL ERROR: ...`, `MONGO ERROR: ...`, `SEARCH ERROR: ...`
- Refusal strings start with `REFUSED: ...` (guardrail triggers)
- Empty results (`[]`, `null`, `""`) generate a warning
- All warnings are collected and returned in the `warnings` array
- The agent loop **never crashes** — this is enforced by `try/except` in every tool

---

## 6. Acceptance Criteria (from SPEC.md §4)

| # | Question | Expected Tool | Must appear in answer |
|---|----------|---------------|----------------------|
| 1 | "What are the top 5 selling products this month?" | `sql_query` | product `name`, `total_sold` |
| 2 | "What are the most common customer complaints this week?" | `mongo_query` | `issue`, `status`, frequency |
| 3 | "What is our return policy for damaged goods?" | `handbook_search` | `section` = "Return & Refund Policy", return window |
| 4 | "Which customers have placed the most orders?" | `sql_query` | customer `name`, `email`, `order_count` |
| 5 | "Show me all 1-star reviews for the Wireless Mouse" | `mongo_query` | `product_id`, `rating`=1, `comment` |

**Failure case:** "What were our sales in 1990?" → `sql_query` returns zero rows → agent reports honestly.

---

## 7. Non-Functional Characteristics

| Property | How it's achieved |
|----------|-------------------|
| **Security** | Read-only tool contracts, SQL keyword guards, Mongo filter whitelist, query limits, statement timeout |
| **Resilience** | No unhandled DB/tool exception can crash the `/chat` endpoint |
| **Observability** | `tool_calls` + `warnings` + `elapsed_ms` make every agent decision inspectable |
| **Latency** | Local embeddings (no API call), Groq sub-second first-token, 5s SQL timeout cap |
| **Maintainability** | Config via `.env`, model swappable via `LLM_MODEL`, tools are independent modules |

---

*Implementation contracts → [LLD.md](./LLD.md) · C4 diagrams → [ARCHITECTURE.md](./ARCHITECTURE.md)*
