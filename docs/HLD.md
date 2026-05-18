# High-Level Design (HLD) — StockPulse Agent

This High-Level Design breaks down the StockPulse Intelligence Agent into its major functional components, defining their responsibilities and how they integrate to fulfill the core use case defined in `SPEC.md`.

---

## 1. System Goals and Non-Functional Requirements

### Primary Goals
1. **Unified Query Interface**: Provide a single conversational entry point for a Store Ops Manager to query structured (SQL), unstructured (NoSQL), and procedural (RAG) data.
2. **Deterministic Tool Usage**: Ensure the agent relies strictly on backend tools rather than LLM memory, avoiding hallucinated data.
3. **Traceability**: Surface the exact tool, arguments, and raw results used by the agent to the frontend so the user can verify the "receipts" of the answer.

### Non-Functional Requirements (NFRs)
- **Security**: Prevent data mutation. Protect against SQL injection and unsafe NoSQL aggregation pipelines.
- **Resilience**: The backend must never crash due to a database exception or malformed agent query. All errors must be stringified and returned to the reasoning loop.
- **Latency**: End-to-end response (including reasoning loop and DB queries) should target < 10 seconds for a single-turn question.
- **Observability**: Maintain a clear logging trail of agent decisions and database queries.

---

## 2. Component Architecture

### 2.1 React SPA Frontend (`frontend/`)
A Vite-based Single Page Application focused entirely on chat interaction.
- **Chat Interface**: Renders user and agent messages. Handles the loading state while the agent reasons.
- **Trace Viewer**: A specialized collapsible React component that renders the `tool_calls` array (Tool Name, Arguments JSON, Result JSON) returned by the API.
- **API Client**: A simple `fetch`-based service layer communicating with the `POST /chat` endpoint.

### 2.2 FastAPI Server Layer (`backend/main.py`)
The HTTP boundary for the backend.
- **Request/Response Validation**: Enforces the JSON payload contract using Pydantic models (e.g., `ChatRequest`, `ChatResponse`).
- **Endpoint Router**: Hosts the `POST /chat` endpoint.
- **Timing and Tracing**: Wraps the agent invocation to calculate `elapsed_ms` and extract `tool_calls` from LangChain's intermediate steps.

### 2.3 ReAct Agent Core (`backend/agent.py`)
The orchestrator that drives the ReAct (Reasoning and Acting) loop.
- **LLM Binding**: Configures `gpt-4o-mini` with temperature 0 (for deterministic tool usage).
- **System Prompt Formulation**: Injects the strict routing rules defined in `SPEC.md` ("Never answer from memory", "Use sql_query for products...").
- **Agent Execution**: Uses LangChain's `create_react_agent` and `AgentExecutor` to manage the thought-action-observation cycle. Max iterations capped at 5 to prevent infinite loops.

### 2.4 Data Tools Layer (`backend/tools/`)
The security and translation boundary between the Agent and the Databases.
- **`sql_tool`**: Receives string SQL. Parses it for dangerous keywords (DROP, DELETE, etc.). Connects to Postgres. Fetches max 50 rows. Formats to JSON.
- **`mongo_tool`**: Receives collection string and filter dict. Validates against a whitelist. Connects to Mongo. Fetches max 20 docs. Formats to JSON.
- **`rag_tool`**: Receives natural language query. Calls OpenAI `text-embedding-3-small`. Queries pgvector for cosine similarity. Returns top 3-5 chunks.

---

## 3. Interaction Protocols

### Agent-to-Tool Protocol
Tools are exposed to the LLM via JSON Schema (derived from Pydantic models). The agent selects a tool and generates a JSON payload. The `AgentExecutor` parses this payload, invokes the Python function, and returns the output *as a string* (the Observation) back to the LLM.

### Error Handling Protocol
1. **Tool-level soft errors**: (e.g., "SQL syntax error"). Caught inside the tool. Returned to the LLM as a string: `"SQL ERROR: syntax error at or near..."`. The LLM reads this and tries again.
2. **Tool-level security faults**: (e.g., "Agent tried to run UPDATE"). Caught by validation. Returned as `"REFUSED: only SELECT statements are allowed"`. The LLM reads this and corrects its approach.
3. **System-level hard errors**: (e.g., "Postgres connection timeout"). Caught by the FastAPI exception handler. Returns a `500 Internal Server Error` to the frontend with a safe message.

---

## 4. Data Topologies

### Transactional & Vector Store (Supabase Postgres)
- Serves as the primary RDBMS.
- Extension `pgvector` enabled on the database.
- Schema explicitly segregated: standard relational tables (`products`, `orders`) for transactional queries, and a dedicated `handbook_chunks` table holding `vector(1536)` columns for RAG.

### Operational Document Store (MongoDB Atlas)
- Serves unstructured telemetry and feedback.
- Used strictly as a Read Replicate equivalent for the agent.
- Schema-less by nature, but tools enforce query validation on specific collections (`reviews`, `activity_logs`).
