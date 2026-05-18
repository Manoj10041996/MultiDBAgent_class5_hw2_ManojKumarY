# High-Level Design (HLD) - StockPulse Agent

This document describes the current architecture of the StockPulse Intelligence Agent and how the main components collaborate.

## 1. System Goals

1. Unified query interface for store operations questions.
2. Deterministic tool usage over SQL, MongoDB, and policy RAG.
3. Traceable answers with tool receipts (`tool_calls`, `warnings`, `elapsed_ms`).

## 2. Runtime Architecture

Browser (React/Vite) -> FastAPI (`/chat`) -> ReAct Agent -> Tools -> Datastores

Tools:
- `sql_query` -> Postgres
- `mongo_query` -> MongoDB
- `handbook_search` -> pgvector policy chunks

## 3. Backend Module Layout

### 3.1 API Layer (`backend/api/`)
- `app.py`: FastAPI app wiring, middleware, `/chat` and `/health` routes.
- `schemas.py`: Pydantic request/response contracts.
- `message_parser.py`: LangGraph message parsing, warning derivation, answer normalization.

### 3.2 Entry Point (`backend/main.py`)
- Thin compatibility module exporting `app` for `uvicorn backend.main:app`.
- Re-exports parser helpers for backward compatibility with existing tests.

### 3.3 Agent Layer (`backend/agent.py`)
- Builds `langgraph.prebuilt.create_react_agent` with Groq model configured in `backend/config.py`.
- Enforces tool-routing and response-style constraints in system prompt.

### 3.4 Tool Layer (`backend/tools/`)
- `sql_tool.py`: read-only SQL execution with guardrails and timeout.
- `mongo_tool.py`: collection/query validation and bounded reads.
- `rag_tool.py`: query embedding + similarity retrieval from policy chunks.

## 4. API Contract

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
Returns:
```json
{ "status": "ok" }
```

## 5. Error and Warning Semantics

- Tool-level failures are returned as strings (`SQL ERROR: ...`, `MONGO ERROR: ...`, `SEARCH ERROR: ...`).
- API warning extraction suppresses transient tool errors if the same tool later succeeds in the same turn.
- Unresolved errors and empty results are surfaced through `warnings`.

## 6. Non-Functional Characteristics

- Security: read-only tool contracts, SQL keyword guards, query limits, execution timeout.
- Resilience: no unhandled DB/tool exceptions should crash the chat endpoint.
- Observability: tool trace and warning payloads make agent behavior inspectable.
- Maintainability: endpoint orchestration, schemas, and parser logic are now separated by concern.
