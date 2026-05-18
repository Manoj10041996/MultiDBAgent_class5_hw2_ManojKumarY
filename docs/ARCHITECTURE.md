# StockPulse Store Intelligence Agent — System Architecture

> Multi-database conversational AI agent for e-commerce store operations.  
> One question in → grounded answer out, with the receipts.

---

## 1. System Context

```mermaid
C4Context
    title System Context — StockPulse Intelligence Agent

    Person(manager, "Store Ops Manager", "Day-to-day inventory, sales, support escalation")

    System(stockpulse, "StockPulse Intelligence Agent", "Conversational AI that unifies SQL, NoSQL, and vector search into a single natural-language interface")

    System_Ext(groq, "Groq API", "openai/gpt-oss-120b — LLM inference")
    SystemDb_Ext(postgres, "Postgres + pgvector", "Products, Orders, Customers + policy_chunks embeddings")
    SystemDb_Ext(mongodb, "MongoDB", "Reviews, Support Tickets, Activity Logs")

    Rel(manager, stockpulse, "Natural language questions", "HTTPS / Browser")
    Rel(stockpulse, groq, "LLM reasoning (ReAct)", "HTTPS / API Key")
    Rel(stockpulse, postgres, "SQL + vector similarity", "TCP / psycopg2")
    Rel(stockpulse, mongodb, "Document queries", "TCP / pymongo")
```

**Note:** Embeddings are generated **locally** using SentenceTransformers (`all-MiniLM-L6-v2`, 384-dim). No external API call is needed for embedding.

---

## 2. Container Diagram

```mermaid
C4Container
    title Container Diagram — StockPulse Intelligence Agent

    Person(manager, "Store Ops Manager")

    Container_Boundary(frontend_boundary, "Frontend") {
        Container(spa, "React SPA", "Vite + React 18 + TypeScript + Tailwind", "Chat UI with tool-call trace panel")
    }

    Container_Boundary(backend_boundary, "Backend") {
        Container(api, "FastAPI Server", "Python 3.12 + Uvicorn", "POST /chat, GET /health, CORS, timing")
        Container(agent, "ReAct Agent", "langgraph.prebuilt.create_react_agent + ChatGroq", "Tool-calling loop, answer synthesis")
        Container(tools, "Tool Layer", "Python + Pydantic @tool", "sql_query, mongo_query, handbook_search")
        Container(embed, "Embedding Engine", "SentenceTransformers all-MiniLM-L6-v2", "Local 384-dim embeddings, no API key")
    }

    Container_Boundary(data_boundary, "Data Stores") {
        ContainerDb(pg, "Postgres", "pgvector extension", "products, orders, customers tables")
        ContainerDb(pgvec, "pgvector Index", "Same Postgres instance", "policy_chunks table — vector(384)")
        ContainerDb(mongo, "MongoDB", "MongoDB 7.0", "reviews, support_tickets, activity_logs")
    }

    System_Ext(groq, "Groq API", "openai/gpt-oss-120b")

    Rel(manager, spa, "Types question", "Browser")
    Rel(spa, api, "POST /chat {question}", "HTTP/JSON")
    Rel(api, agent, "Invokes agent with messages")
    Rel(agent, tools, "Calls tools via ReAct loop")
    Rel(tools, pg, "SELECT queries", "psycopg2")
    Rel(tools, pgvec, "Cosine similarity search", "psycopg2")
    Rel(tools, mongo, "find() queries", "pymongo")
    Rel(agent, groq, "LLM reasoning", "HTTPS")
    Rel(tools, embed, "Query embedding", "in-process")
    Rel(api, spa, "{answer, tool_calls, warnings, elapsed_ms}", "HTTP/JSON")
```

---

## 3. Single-Request Lifecycle

```mermaid
sequenceDiagram
    participant U as Store Manager
    participant FE as React Frontend
    participant API as FastAPI Server
    participant AG as ReAct Agent
    participant LLM as Groq (gpt-oss-120b)
    participant TL as Tool Layer
    participant DB as Data Store

    U->>FE: Types question + presses Enter
    FE->>API: POST /chat {"question": "..."}

    Note over API: Start timer, validate via Pydantic

    API->>AG: agent.invoke({"messages": [("user", question)]})

    loop ReAct Loop (max 5 iterations)
        AG->>LLM: System prompt + messages + tool definitions
        LLM-->>AG: AIMessage with tool_calls[]
        AG->>TL: Execute tool (validated args)

        alt sql_query
            TL->>TL: Validate SQL (no writes, no multi-stmt)
            TL->>DB: Execute SELECT with 5s timeout
            DB-->>TL: Result rows (max 50)
        else mongo_query
            TL->>TL: Validate collection whitelist + filter safety
            TL->>DB: collection.find(filter).limit(20)
            DB-->>TL: Documents (max 20)
        else handbook_search
            TL->>TL: Embed query locally (all-MiniLM-L6-v2)
            TL->>DB: pgvector cosine similarity search
            DB-->>TL: Top-k chunks with sections
        end

        TL-->>AG: ToolMessage (always string, never crashes)
    end

    AG->>LLM: Final reasoning with all observations
    LLM-->>AG: AIMessage (final answer, no tool_calls)
    AG-->>API: {"messages": [...full conversation...]}

    Note over API: Stop timer, extract tool trace from messages

    API-->>FE: {answer, tool_calls, warnings, elapsed_ms}
    FE-->>U: Render answer + expandable tool trace
```

---

## 4. Deployment Topology

```mermaid
graph TB
    subgraph "Developer Machine"
        FE["Vite Dev Server<br/>localhost:5173"]
        BE["Uvicorn + FastAPI<br/>localhost:8000"]
        EMB["SentenceTransformers<br/>all-MiniLM-L6-v2<br/>(in-process, CPU)"]
    end

    subgraph "Docker Compose"
        PG["Postgres 16 + pgvector<br/>localhost:5432"]
        MG["MongoDB 7.0<br/>localhost:27017"]
    end

    subgraph "Cloud"
        GROQ["Groq API<br/>api.groq.com"]
    end

    FE -->|"POST /chat<br/>(Vite proxy)"| BE
    BE -->|"LLM inference"| GROQ
    BE -->|"SQL + Vector"| PG
    BE -->|"Document queries"| MG
    BE --- EMB

    style FE fill:#3b82f6,color:#fff
    style BE fill:#10b981,color:#fff
    style EMB fill:#8b5cf6,color:#fff
    style GROQ fill:#6366f1,color:#fff
    style PG fill:#f59e0b,color:#fff
    style MG fill:#22c55e,color:#fff
```

---

## 5. Security Boundaries

```mermaid
graph LR
    subgraph "Trust Zone: Browser"
        USER["User Input"]
    end

    subgraph "Trust Zone: Backend"
        VALIDATE["Pydantic<br/>Validation"]
        AGENT["ReAct Agent<br/>(ChatGroq)"]
        TOOLS["Tool Layer<br/>(Sandboxed)"]
    end

    subgraph "Trust Zone: Data"
        PG["Postgres<br/>(Read-Only)"]
        MG["MongoDB<br/>(Read-Only)"]
    end

    USER -->|"POST /chat"| VALIDATE
    VALIDATE -->|"Sanitized question"| AGENT
    AGENT -->|"Tool calls"| TOOLS

    TOOLS -->|"Validated SELECT only"| PG
    TOOLS -->|"Whitelisted collection<br/>+ safe filter"| MG

    style USER fill:#ef4444,color:#fff
    style VALIDATE fill:#f59e0b,color:#fff
    style AGENT fill:#10b981,color:#fff
    style TOOLS fill:#10b981,color:#fff
    style PG fill:#3b82f6,color:#fff
    style MG fill:#3b82f6,color:#fff
```

### Guardrail Summary

| Layer | Guardrail | Implementation |
|-------|-----------|----------------|
| HTTP | Max question length 1000 chars | Pydantic `Field(max_length=1000)` |
| SQL | 11 forbidden keywords (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, GRANT, REVOKE, CREATE, EXEC, EXECUTE) | `_validate_sql()` regex check |
| SQL | Multi-statement injection | Semicolon splitting after strip |
| SQL | Runaway queries | Auto-LIMIT 50, `statement_timeout=5000ms` |
| Mongo | Collection whitelist | Only `reviews`, `support_tickets`, `activity_logs` |
| Mongo | NoSQL injection | Recursive `$where`, `$function`, `$accumulator` check |
| Mongo | Result cap | Hard limit 20 documents |
| RAG | Noise suppression | Similarity threshold (0.2) filters irrelevant chunks |
| RAG | Result cap | Max k=5 chunks |
| All tools | Crash prevention | Every tool returns a string — exceptions are caught |

---

## 6. Project Directory Structure

```
MultiDBAgent_class5_hw2_ManojKumarY/
│
├── SPEC.md                         # Specification (committed first)
├── README.md                       # Setup, architecture, decisions, findings
├── .env.example                    # Environment template (no secrets)
├── pyproject.toml                  # Python deps (uv)
├── docker-compose.yml              # Postgres (pgvector) + MongoDB containers
│
├── docs/
│   ├── ARCHITECTURE.md             # This file
│   ├── HLD.md                      # High-Level Design
│   └── LLD.md                      # Low-Level Design
│
├── backend/
│   ├── __init__.py
│   ├── config.py                   # Pydantic Settings (Groq key, DB URLs, limits)
│   ├── main.py                     # FastAPI app, POST /chat, GET /health
│   ├── agent.py                    # create_react_agent + ChatGroq + system prompt
│   └── tools/
│       ├── __init__.py
│       ├── sql_tool.py             # Read-only SQL with guardrails
│       ├── mongo_tool.py           # Whitelisted MongoDB queries
│       └── rag_tool.py             # SentenceTransformer + pgvector search
│
├── scripts/
│   ├── seed_postgres.py            # Products, customers, orders
│   ├── seed_mongo.py               # Reviews, support_tickets, activity_logs
│   └── index_policies.py           # Chunk + embed policies → policy_chunks
│
├── policies/
│   ├── return_refund.md
│   ├── shipping.md
│   └── discounts.md
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── vite.config.ts              # Dev proxy /chat → localhost:8000
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                  # Full chat UI, message history, suggestions
│       ├── index.css
│       ├── api/
│       │   └── chat.ts             # POST /chat API client
│       ├── components/
│       │   ├── ToolTrace.tsx        # Expandable tool-call trace panel
│       │   └── WarningBanner.tsx    # Amber guardrail warning badges
│       └── types/
│           └── index.ts            # TypeScript interfaces matching API contract
│
└── tests/
    ├── __init__.py
    ├── conftest.py                  # Shared fixtures (env-based skip logic)
    ├── unit/
    │   ├── __init__.py
    │   ├── test_sql_tool.py         # 11 tests: validation, LIMIT, mocked DB
    │   ├── test_mongo_tool.py       # 9 tests: whitelist, injection, cap
    │   └── test_rag_tool.py         # 9 tests: embedding, threshold, errors
    └── e2e/
        ├── __init__.py
        └── test_agent_e2e.py        # 5 acceptance + 1 failure + 4 contract
```

---

## 7. Key Architectural Decisions

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Agent never touches DB directly | Tools are the only data interface | Enforces ReAct pattern. Agent sees string results, never connection objects. Prevents prompt-injection escalation. |
| 2 | Tools always return strings | Even on error, tools return a descriptive string | Prevents the ReAct loop from crashing. Agent reasons about errors gracefully. |
| 3 | LLM: Groq API | `openai/gpt-oss-120b` via `ChatGroq` | Sub-second first-token latency. Strong ReAct instruction following. Swappable via `LLM_MODEL` in `.env`. |
| 4 | Embeddings: local SentenceTransformers | `all-MiniLM-L6-v2` (384-dim, CPU) | Eliminates external API dependency for embeddings. 90 MB model, zero cost per query. |
| 5 | pgvector in same Postgres | Policy chunks alongside transactional data | Single DB instance simplifies ops. No separate vector DB needed at this scale (<100 chunks). |
| 6 | Single `/chat` endpoint | No REST resources, no CRUD | The agent IS the API. One question in, one grounded answer out. |
| 7 | Pydantic everywhere | Tool args, HTTP request/response, config | Type safety from HTTP boundary to tool invocation. Validation errors surface before any DB call. |
| 8 | Vector dimension: 384 | Matches `all-MiniLM-L6-v2` output | DDL uses `vector(384)`. If embedding model changes, re-run `index_policies.py`. |

---

*Component-level design → [HLD.md](./HLD.md) · Implementation contracts → [LLD.md](./LLD.md)*
