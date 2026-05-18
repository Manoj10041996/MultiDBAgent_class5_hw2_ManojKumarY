# Low-Level Design (LLD) — StockPulse Agent

> Implementation-level contracts mapping SPEC.md to exact code. Every code
> snippet here reflects the **actual running codebase**, not aspirational design.
>
> For component overview see [HLD.md](./HLD.md). For C4 diagrams see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## 1. API Layer (`backend/main.py`)

### 1.1 Pydantic Models

```python
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)

class ToolCallRecord(BaseModel):
    tool: str          # "sql_query" | "mongo_query" | "handbook_search"
    args: Any          # arguments passed to the tool
    result: str        # raw string result returned by the tool

class ChatResponse(BaseModel):
    answer: str                       # agent's final answer
    tool_calls: list[ToolCallRecord]  # every tool invocation in order
    warnings: list[str]               # guardrail triggers, empty results
    elapsed_ms: int                   # wall-clock time (ms)
```

### 1.2 Endpoint Implementation

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    start_ms = time.time()

    result = agent.invoke(
        {"messages": [("user", request.question)]},
        config={"recursion_limit": settings.agent_max_iterations * 2 + 2},
    )

    messages = result.get("messages", [])
    answer = _get_final_answer(messages)
    tool_calls, warnings = _extract_tool_calls(messages)

    return ChatResponse(
        answer=answer,
        tool_calls=tool_calls,
        warnings=warnings,
        elapsed_ms=int((time.time() - start_ms) * 1000),
    )
```

### 1.3 Message Parsing (`_extract_tool_calls`)

The LangGraph agent returns a `messages` list. Parsing logic:

1. **Index** all `ToolMessage` objects by `tool_call_id` → `dict[str, str]`
2. **Walk** each `AIMessage` that has `.tool_calls`
3. **Pair** each tool call with its corresponding `ToolMessage.content`
4. **Flag warnings** for: `REFUSED:*`, `SQL ERROR:*`, `MONGO ERROR:*`, `SEARCH ERROR:*`, empty results

### 1.4 Answer Extraction (`_get_final_answer`)

Walk `messages` in reverse, return the content of the **last `AIMessage`** that
has no `tool_calls` — this is the agent's final grounded answer.

---

## 2. Agent Configuration (`backend/agent.py`)

### 2.1 LLM Setup

```python
from langchain_groq import ChatGroq

llm = ChatGroq(
    model=settings.llm_model,           # "openai/gpt-oss-120b"
    temperature=0,
    groq_api_key=settings.groq_api_key,
)
```

**Why Groq?** Sub-second first-token latency. The `openai/gpt-oss-120b` model
has strong ReAct instruction following. Swappable via `LLM_MODEL` in `.env`
(per SPEC.md Appendix: Model Swap Policy).

### 2.2 Agent Construction

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    model=llm,
    tools=[sql_query, mongo_query, handbook_search],
    prompt=SYSTEM_PROMPT,   # exact text from SPEC.md §3
)
```

Returns a `CompiledStateGraph`. Invoked with:
```python
result = agent.invoke(
    {"messages": [("user", question)]},
    config={"recursion_limit": 12},   # 5 iterations × 2 nodes + 2 buffer
)
```

### 2.3 System Prompt

The system prompt is the **exact text from SPEC.md §3**, including:
- Tool selection routing rules
- Hard rules (no memory, cite exact values, one paragraph)

---

## 3. Tool Implementation Details (`backend/tools/`)

All tools use LangChain's `@tool` decorator for auto-generated JSON schemas.
All tools return strings — the agent loop **never crashes**.

### 3.1 SQL Tool (`sql_tool.py`)

```python
@tool
def sql_query(sql: str) -> str:
    """Execute read-only SELECT against Postgres."""
```

**Validation pipeline (in order):**

| Step | Check | On failure |
|------|-------|------------|
| 1 | Strip and normalize whitespace | — |
| 2 | Reject forbidden keywords: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`, `CREATE`, `EXEC`, `EXECUTE` | `"REFUSED: query contains forbidden keyword {kw}"` |
| 3 | Reject multiple statements: split on `;`, check count | `"REFUSED: multiple statements not allowed"` |
| 4 | Must start with `SELECT` or `WITH` | `"REFUSED: only SELECT statements are allowed"` |
| 5 | Auto-inject `LIMIT 50` if no LIMIT present and no aggregate (`GROUP BY`, `COUNT`, `SUM`, `AVG`, `MAX`, `MIN`) | — |

**Execution:**
```python
conn = psycopg2.connect(settings.postgres_url, options="-c statement_timeout=5000")
cur.execute(validated_sql)
rows = [dict(zip(columns, row)) for row in cur.fetchall()]
return json.dumps(rows, default=str)
```

**Error handling:** `except Exception as e: return f"SQL ERROR: {e}"`

### 3.2 MongoDB Tool (`mongo_tool.py`)

```python
@tool
def mongo_query(collection: str, filter: dict, limit: int = 10) -> str:
    """Query MongoDB collections for reviews, tickets, and logs."""
```

**Validation pipeline:**

| Step | Check | On failure |
|------|-------|------------|
| 1 | Collection whitelist: `reviews`, `support_tickets`, `activity_logs` | `"REFUSED: collection '{name}' not whitelisted"` |
| 2 | Recursive filter key scan for `$where`, `$function`, `$accumulator` | `"REFUSED: server-side JS not allowed"` |
| 3 | Hard cap: `limit = min(limit, 20)` | Silent cap |

**Execution:**
```python
client = pymongo.MongoClient(settings.mongo_url)
docs = list(client[settings.mongo_db][collection].find(filter).limit(limit))
return json.dumps(docs, default=str)
```

**Error handling:** `except Exception as e: return f"MONGO ERROR: {e}"`

### 3.3 RAG Tool (`rag_tool.py`)

```python
@tool
def handbook_search(query: str, k: int = 3) -> str:
    """Semantic search over policy documents using local embeddings."""
```

**Embedding engine (module-level singleton):**
```python
from sentence_transformers import SentenceTransformer

_model = SentenceTransformer(settings.embedding_model_name)  # all-MiniLM-L6-v2

def _embed(text: str) -> list[float]:
    return _model.encode(text).tolist()  # returns 384-dim vector
```

**No external API call needed.** The model is downloaded once (~90 MB) and runs
on CPU in-process.

**Execution pipeline:**

| Step | Action |
|------|--------|
| 1 | Cap `k = min(k, 5)` |
| 2 | Embed query locally: `_embed(query)` → 384-dim vector |
| 3 | Query pgvector: `SELECT section, chunk, 1 - (embedding <=> %s) AS similarity FROM policy_chunks ORDER BY embedding <=> %s LIMIT %s` |
| 4 | Filter by threshold: discard rows with `similarity < 0.2` |
| 5 | Format: `json.dumps([{"section": r[0], "chunk": r[1]}])` |

**Error handling:** `except Exception as e: return f"SEARCH ERROR: {e}"`

**Important:** The `policy_chunks` table uses `vector(384)` to match
`all-MiniLM-L6-v2` output. If the embedding model is changed, the table
DDL must be updated and `scripts/index_policies.py` re-run.

---

## 4. Configuration (`backend/config.py`)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str                           # required
    postgres_url: str                            # required
    mongo_url: str                               # required
    mongo_db: str = "stockpulse"

    llm_model: str = "openai/gpt-oss-120b"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    agent_max_iterations: int = 5
    sql_row_limit: int = 50
    sql_timeout_ms: int = 5000
    mongo_doc_limit: int = 20
```

---

## 5. Data Seeding Scripts (`scripts/`)

### 5.1 `seed_postgres.py`
Creates tables `products`, `customers`, `orders` with realistic e-commerce data.
Schema matches SPEC.md §2 exactly.

### 5.2 `seed_mongo.py`
Populates collections `reviews`, `support_tickets`, `activity_logs` with
documents matching SPEC.md §2 collection schemas.

### 5.3 `index_policies.py`
1. Reads markdown files from `policies/` directory
2. Chunks each document (~300 tokens, 50 token overlap) per SPEC.md §2
3. Embeds each chunk locally using `SentenceTransformer("all-MiniLM-L6-v2")`
4. Creates `policy_chunks` table with `vector(384)` column
5. Inserts `(section, chunk, embedding)` rows

---

## 6. Frontend (`frontend/src/`)

### 6.1 State Management (React)

```typescript
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallRecord[];
  warnings?: string[];
  elapsedMs?: number;
}

// SPEC.md §6: single-turn, no persistence across page reloads
const [messages, setMessages] = useState<ChatMessage[]>([]);
const [isLoading, setIsLoading] = useState(false);
```

### 6.2 API Client (`api/chat.ts`)

```typescript
const API_BASE = import.meta.env.VITE_API_URL ?? '';

export async function sendQuestion(question: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? `HTTP ${res.status}`);
  return res.json();
}
```

Uses relative URL in dev → Vite proxy forwards to `localhost:8000`.

### 6.3 Tool Trace (`ToolTrace.tsx`)

Per SPEC.md §6: expandable panel showing tool name, args, and raw result.
Truncates result strings to 500 chars to prevent UI blowout.

### 6.4 Warning Display (`WarningBanner.tsx`)

Per SPEC.md §6: muted amber banner below the answer for each warning string.

---

## 7. Testing (`tests/`)

### 7.1 Unit Tests (`tests/unit/`)

All mock external dependencies. No live DB or LLM needed.

| File | Tests | What's validated |
|------|-------|------------------|
| `test_sql_tool.py` | 11 | Keyword rejection, LIMIT injection, aggregate skip, multi-statement block, timeout handling |
| `test_mongo_tool.py` | 9 | Whitelist enforcement, `$where` injection, cap enforcement, ObjectId serialization |
| `test_rag_tool.py` | 9 | Local embedding mock (384-dim), threshold filtering, k-cap, error handling |

### 7.2 E2E Tests (`tests/e2e/test_agent_e2e.py`)

Runs the 5 acceptance questions from SPEC.md §4 + the failure case against live
databases. Each test asserts:

1. Correct tool was called (`tool_calls[0].tool == expected`)
2. Answer contains required fields
3. No hallucinated data

| # | Question | Expected Tool |
|---|----------|---------------|
| 1 | "What are the top 5 selling products this month?" | `sql_query` |
| 2 | "What are the most common customer complaints this week?" | `mongo_query` |
| 3 | "What is our return policy for damaged goods?" | `handbook_search` |
| 4 | "Which customers have placed the most orders?" | `sql_query` |
| 5 | "Show me all 1-star reviews for the Wireless Mouse" | `mongo_query` |
| F | "What were our sales in 1990?" | `sql_query` → 0 rows → honest "no data" |

---

*Component overview → [HLD.md](./HLD.md) · C4 diagrams → [ARCHITECTURE.md](./ARCHITECTURE.md)*
