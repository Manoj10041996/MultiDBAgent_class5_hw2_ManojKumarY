# SPEC.md — StockPulse Store Intelligence Agent

> Inspired by how enterprise e-commerce platforms like Shopify, Amazon Seller 
> Central, and Salesforce Commerce Cloud give store managers a single pane of 
> glass over sales, support, and policy — StockPulse brings that same 
> intelligence to a single conversational agent.

---

## 1. Problem Statement

### Who is the user?

A **StockPulse Store Operations Manager** — the person responsible for the 
day-to-day health of an e-commerce business. They sit between the data 
(Postgres for transactions, MongoDB for customer interactions) and the 
decisions (what to restock, which complaints to escalate, how to apply 
the return policy).

Today they switch between three systems to answer one question:
- Open the analytics dashboard to check sales
- Open the support portal to read tickets
- Open a shared drive to find the policy PDF

StockPulse collapses that into one question, one answer, with receipts.

### What kinds of questions do they ask?

**Sales & Inventory (→ SQL)**
- "What are the top 5 selling products this month?"
- "Which products are running low on stock?"
- "What is our total revenue this week?"

**Customer Feedback & Support (→ MongoDB)**
- "What are customers complaining about most this week?"
- "Show me all open support tickets about delayed shipments"
- "Show me all 1-star reviews for the Wireless Mouse"

**Policy & Procedures (→ RAG)**
- "What is our return policy for damaged goods?"
- "Does our shipping policy cover international orders?"
- "What discount rules apply to bulk orders?"

### Business Impact

Without this agent, a store manager spends 30-45 minutes per shift 
context-switching between systems to answer questions that should take 
seconds. StockPulse reduces that to a single natural language query.

---

## 2. The 3 Tools and Their Contracts

### Tool 1: `sql_query`

**Purpose:**
Query structured transactional data — products, orders, customers — 
from a Postgres database. This is the source of truth for all 
financial and inventory data.

**Real-world equivalent:** Shopify Analytics SQL, Amazon Seller Central Reports

**Input arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `sql` | `str` | Yes | A read-only SELECT query against the StockPulse schema |

**Return shape:**
```json
[
  {
    "name": "Wireless Mouse",
    "category": "Electronics",
    "total_sold": 320,
    "revenue": 9600.00
  },
  {
    "name": "USB Hub",
    "category": "Electronics", 
    "total_sold": 285,
    "revenue": 5700.00
  }
]
```
Returns a JSON-serializable list of dicts. Maximum 50 rows.
Auto-injects `LIMIT 50` if no LIMIT clause and query is not an aggregate.
Has a 5-second statement timeout.

**How errors are surfaced:**

| Scenario | Return value |
|----------|-------------|
| Forbidden keyword (DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE) | `"REFUSED: query contains forbidden keyword DROP"` |
| Non-SELECT statement | `"REFUSED: only SELECT statements are allowed"` |
| Multiple statements (`;` mid-query) | `"REFUSED: multiple statements not allowed"` |
| Postgres execution error | `"SQL ERROR: <postgres error message>"` |
| Statement timeout | `"SQL ERROR: statement timeout exceeded"` |

Tool always returns a string — agent loop never crashes.

**Database Schema:**
```sql
products  (id SERIAL PK, name TEXT, category TEXT, 
           price NUMERIC, stock_qty INT)

orders    (id SERIAL PK, customer_id INT FK, product_id INT FK,
           quantity INT, total NUMERIC, status TEXT, 
           created_at TIMESTAMPTZ)

customers (id SERIAL PK, name TEXT, email TEXT, city TEXT)
```

---

### Tool 2: `mongo_query`

**Purpose:**
Query unstructured operational data — customer reviews, support tickets,
activity logs — from MongoDB Atlas. This is the source of truth for 
customer sentiment and support operations.

**Real-world equivalent:** Zendesk ticket query, Trustpilot review API, 
Segment activity logs

**Input arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `collection` | `str` | Yes | One of: `reviews`, `support_tickets`, `activity_logs` |
| `filter` | `dict` | Yes | MongoDB filter document e.g. `{"rating": 1}` |
| `limit` | `int` | No | Max documents. Default 10, hard cap 20 |

**Return shape:**
```json
[
  {
    "customer_id": "C042",
    "issue": "Wrong item delivered",
    "status": "open",
    "created_at": "2026-05-01T10:23:00Z"
  },
  {
    "customer_id": "C087",
    "issue": "Package arrived damaged",
    "status": "in_progress",
    "created_at": "2026-05-02T14:11:00Z"
  }
]
```
Returns a JSON-serializable list of MongoDB documents.

**How errors are surfaced:**

| Scenario | Return value |
|----------|-------------|
| Collection not in whitelist | `"REFUSED: collection 'orders' not whitelisted"` |
| Filter contains `$where` or `$function` | `"REFUSED: server-side JS not allowed"` |
| Unsafe aggregation stage | `"REFUSED: aggregation stage '$out' not allowed"` |
| MongoDB execution error | `"MONGO ERROR: <error message>"` |

Tool always returns a string — agent loop never crashes.


**Collection Schemas:**

```python
reviews (
  product_id: str,
  customer_id: str,
  rating: int,        # 1-5
  comment: str,
  date: datetime
)

support_tickets (
  ticket_id: str,
  customer_id: str,
  issue: str,
  status: str,        # open | in_progress | resolved
  created_at: datetime
)

activity_logs (
  user_id: str,
  action: str,        # view | add_to_cart | purchase | wishlist
  product_id: str,
  page: str,
  timestamp: datetime
)
```
**Safe aggregation stages (if aggregation enabled):**
`$match`, `$group`, `$sort`, `$limit`, `$project` only.
No `$out`, `$merge`, `$lookup` with external collections, or `$where`.

---

### Tool 3: `handbook_search`

**Purpose:**
Semantic vector search over StockPulse internal policy documents using 
pgvector and OpenAI text-embedding-3-small embeddings. Returns the most 
relevant policy chunks for a natural language question.

**Real-world equivalent:** Notion AI policy search, Confluence knowledge 
base RAG, Zendesk Help Center semantic search

**Input arguments:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | `str` | Yes | Natural language question to search policy documents |
| `k` | `int` | No | Number of chunks to return. Default 3, max 5 |

**Return shape:**
```json
[
  {
    "section": "Return & Refund Policy",
    "chunk": "Damaged goods may be returned within 30 days of delivery. 
              The customer must provide photo evidence of the damage 
              at the time of filing the return request..."
  },
  {
    "section": "Return & Refund Policy", 
    "chunk": "Refunds are processed within 5-7 business days after the 
              returned item is received and inspected at our warehouse..."
  }
]
```
Returns a list of dicts with `section` label and `chunk` text.

**How errors are surfaced:**

| Scenario | Return value |
|----------|-------------|
| No relevant chunks found (similarity below threshold) | `[]` empty list |
| Embedding API error | `"SEARCH ERROR: embedding failed - <message>"` |
| pgvector query error | `"SEARCH ERROR: vector search failed - <message>"` |

Tool always returns a string or list — agent loop never crashes.

**Documents Indexed:**

| Document | Sections | Approx chunks |
|----------|----------|---------------|
| Return & Refund Policy | Eligibility, Process, Timelines, Exceptions | 8 chunks |
| Shipping Policy | Domestic, International, Express, Delays | 6 chunks |
| Discount & Promotions Policy | Bulk orders, Seasonal, Loyalty, Stacking rules | 5 chunks |

Chunk size: ~300 tokens. Overlap: 50 tokens.

---


## 3. Routing Rules

The following is the exact system prompt the agent receives:

```
You are the StockPulse Store Intelligence Agent — an internal tool 
for store operations managers at StockPulse e-commerce.

You have access to three tools. Use them according to these rules:

TOOL SELECTION:
- sql_query: use for any question about products, orders, sales, 
  revenue, stock levels, customers, quantities, dates, totals, 
  rankings, or any structured transactional data.

- mongo_query: use for any question about customer reviews, star 
  ratings, complaints, support tickets, refund requests, return 
  complaints, or user activity and behaviour logs.

- handbook_search: use for any question about store policies, 
  return rules, shipping terms, discount eligibility, promotion 
  conditions, or any procedural or compliance question.

HARD RULES:
- Never answer from memory or training data. Always use a tool.
- Do not call a tool if a previous tool result already answers 
  the question.
- If a tool returns an error or empty result, report it honestly. 
- Cite exact numbers and field values returned by the tools.
- Answer in one short paragraph.
```

---

## 4. Definition of Done

The following five questions constitute the acceptance test suite. 
Each will be run as an e2e test. A question passes if:
- The correct tool is called
- The answer contains the specified fields
- No hallucinated data appears in the answer

| # | Question | Expected Tool | Fields that must appear in answer |
|---|----------|---------------|----------------------------------|
| 1 | "What are the top 5 selling products this month?" | `sql_query` | product `name`, `total_sold` quantity |
| 2 | "What are the most common customer complaints this week?" | `mongo_query` | `issue` text, `status`, complaint frequency |
| 3 | "What is our return policy for damaged goods?" | `handbook_search` | `section` = "Return & Refund Policy", `chunk` with return window and conditions |
| 4 | "Which customers have placed the most orders?" | `sql_query` | customer `name`, `email`, `order_count` |
| 5 | "Show me all 1-star reviews for the Wireless Mouse" | `mongo_query` | `product_id`, `rating` = 1, `comment`, `date` |

**Failure case (must be demoed):**
Ask: "What were our sales in 1990?"
Expected: agent queries sql_query, gets zero rows, honestly reports 
no data found. Must NOT hallucinate sales figures.

---

## 5. API Contract

### Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| HTTP server | **FastAPI** | Assignment requirement. Async-native, auto-generates OpenAPI docs. |
| Agent framework | **LangChain v1** (`create_react_agent`) | Assignment requirement. ReAct loop with typed tool bindings. |
| LLM | **OpenAI gpt-4o-mini** (default) | Assignment default. Low cost, fast enough for single-turn. May swap to `gpt-4o` if tool-calling accuracy is poor — will document in README if so. |
| Embeddings | **OpenAI text-embedding-3-small** | Specified in §2 for `handbook_search`. Same provider simplifies key management. |

### Endpoint

```
POST /chat
Content-Type: application/json
```

**Request body:**
```json
{
  "question": "What are the top 5 selling products this month?"
}
```

**Response body:**
```json
{
  "answer": "The top 5 selling products this month are: 1. Wireless Mouse (320 units)...",
  "tool_calls": [
    {
      "tool": "sql_query",
      "args": {
        "sql": "SELECT p.name, SUM(o.quantity) AS total_sold FROM products p JOIN orders o ON p.id = o.product_id WHERE o.created_at >= date_trunc('month', CURRENT_DATE) GROUP BY p.name ORDER BY total_sold DESC LIMIT 5"
      },
      "result": "[{\"name\": \"Wireless Mouse\", \"total_sold\": 320}, ...]"
    }
  ],
  "warnings": [],
  "elapsed_ms": 2340
}
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `answer` | `str` | The agent's final natural-language answer |
| `tool_calls` | `list[ToolCall]` | Every tool invocation: tool name, arguments passed, raw result returned |
| `warnings` | `list[str]` | Any guardrail triggers, empty results, or soft errors the frontend should surface |
| `elapsed_ms` | `int` | Wall-clock time from request received to response sent |

**Error responses:**

| Status | When |
|--------|------|
| `422` | Missing or malformed `question` field |
| `500` | Unrecoverable agent error (LLM API down, DB unreachable) — returns `{"error": "..."}` |

### CORS

Allow `http://localhost:5173` (Vite dev server) in development.

---

## 6. Frontend

### Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Build tool | **Vite** | Assignment recommendation. Fast HMR, zero-config TypeScript. |
| UI framework | **React 18 + TypeScript** | Assignment requirement. |
| Styling | **Tailwind CSS** | Assignment recommendation. Utility-first, no custom CSS files to manage. |

### What the UI shows

The chat interface displays three things per interaction:

1. **User question** — the query as typed
2. **Agent answer** — the final natural-language response
3. **Tool call trace** — expandable panel showing:
   - Which tool was called (e.g. `sql_query`)
   - The arguments passed (e.g. the SQL string)
   - The raw result returned (truncated if long)

### UI behaviour

- Single-turn only. No conversation memory, no chat history 
  across page reloads.
- No authentication required.
- No streaming required. The UI shows a loading spinner while 
  waiting for `POST /chat` to return, then renders the full 
  response.
- If the backend returns a `warnings` array, display each warning 
  as a muted banner below the answer.
- If the backend returns a 500, show a user-friendly error message.

### Layout (minimal)

```
┌──────────────────────────────────────┐
│  StockPulse Intelligence Agent       │
├──────────────────────────────────────┤
│                                      │
│  [Chat messages area]                │
│                                      │
│  ┌─ User ──────────────────────────┐ │
│  │ What are the top 5 selling      │ │
│  │ products this month?            │ │
│  └─────────────────────────────────┘ │
│                                      │
│  ┌─ Agent ─────────────────────────┐ │
│  │ The top 5 selling products...   │ │
│  │                                 │ │
│  │ ▸ Tool trace (click to expand)  │ │
│  │   ┌─ sql_query ──────────────┐  │ │
│  │   │ args: SELECT p.name ...  │  │ │
│  │   │ result: [{...}, ...]     │  │ │
│  │   └──────────────────────────┘  │ │
│  └─────────────────────────────────┘ │
│                                      │
├──────────────────────────────────────┤
│  [________________] [Ask]            │
└──────────────────────────────────────┘
```

---

## 7. Test Plan

### Structure

```
tests/
├── unit/
│   ├── test_sql_tool.py
│   ├── test_mongo_tool.py
│   └── test_rag_tool.py
├── integration/
│   ├── test_sql_integration.py
│   ├── test_mongo_integration.py
│   └── test_rag_integration.py
└── e2e/
    └── test_agent_e2e.py
```

### Unit tests (`tests/unit/`)

Mock external dependencies (database connections, LLM calls). 
Use LangChain's `GenericFakeChatModel` for LLM mocking.

**Per tool, test three categories:**

| Category | Example |
|----------|---------|
| Good input | `sql_query("SELECT name FROM products LIMIT 5")` → returns list of dicts |
| Malformed input | `sql_query("SELEC name FORM products")` → returns `"SQL ERROR: ..."` |
| Dangerous input | `sql_query("DROP TABLE products")` → returns `"REFUSED: ..."` |

**`mongo_query` unit tests additionally cover:**
- Collection not in whitelist → `"REFUSED: ..."`
- Filter with `$where` → `"REFUSED: ..."`
- Limit exceeds hard cap → silently capped to 20

**`handbook_search` unit tests additionally cover:**
- Empty query string → returns `[]` or error
- k > 5 → silently capped to 5

### Integration tests (`tests/integration/`)

Hit real test databases (Postgres, MongoDB) seeded with known data.
Each test verifies the full tool function against live infrastructure.

| Test | Verifies |
|------|----------|
| SQL: select known product | Returns correct row from seeded data |
| SQL: statement timeout | Query with `pg_sleep(10)` returns timeout error |
| Mongo: query seeded reviews | Returns expected documents |
| Mongo: whitelist enforcement | Rejects non-whitelisted collection |
| RAG: search seeded policy | Returns chunks from correct section |

### End-to-end tests (`tests/e2e/`)

Run the 5 sample questions from §4 through the full agent loop 
(LangChain agent → tool → real database → response).

Each test asserts:
1. The correct tool was called (check `tool_calls` in response)
2. The answer contains the expected fields
3. No hallucinated data appears

Plus the failure case: "What were our sales in 1990?" must return 
an honest "no data found" answer, not fabricated numbers.

---

## Appendix: Model Swap Policy

The assignment default is `gpt-4o-mini`. If tool-calling accuracy 
is insufficient during development, the model may be swapped to 
`gpt-4o` or `claude-sonnet-4-20250514`. Any swap will be:
- Documented in README under "Why I chose X"
- Justified with specific failure examples from the original model
- The `.env.example` will list the model as a configurable variable
