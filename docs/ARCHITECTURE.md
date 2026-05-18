# StockPulse Store Intelligence Agent — System Architecture

> Enterprise-grade multi-database conversational agent for e-commerce operations intelligence.

---

## 1. System Context Diagram

```mermaid
C4Context
    title System Context — StockPulse Intelligence Agent

    Person(manager, "Store Ops Manager", "Day-to-day e-commerce operations, inventory, support escalation")
    
    System(stockpulse, "StockPulse Intelligence Agent", "Conversational AI agent that unifies SQL, NoSQL, and vector search into a single natural-language interface")

    System_Ext(openai, "OpenAI API", "GPT-4o-mini for reasoning, text-embedding-3-small for embeddings")
    SystemDb_Ext(postgres, "Supabase Postgres", "Products, Orders, Customers + pgvector handbook embeddings")
    SystemDb_Ext(mongodb, "MongoDB Atlas", "Reviews, Support Tickets, Activity Logs")

    Rel(manager, stockpulse, "Asks natural language questions", "HTTPS / Browser")
    Rel(stockpulse, openai, "LLM inference + embedding", "HTTPS / API Key")
    Rel(stockpulse, postgres, "SQL queries + vector search", "TCP / connection string")
    Rel(stockpulse, mongodb, "Document queries", "TCP / connection string")
```

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
        Container(api, "FastAPI Server", "Python 3.12 + FastAPI + Uvicorn", "POST /chat endpoint, request validation, CORS, timing")
        Container(agent, "LangChain ReAct Agent", "LangChain v1 create_react_agent", "ReAct reasoning loop, tool dispatch, answer synthesis")
        Container(tools, "Tool Layer", "Python + Pydantic", "sql_query, mongo_query, handbook_search — typed, validated, sandboxed")
    }

    Container_Boundary(data_boundary, "Data Stores") {
        ContainerDb(pg, "Postgres", "Supabase Postgres", "products, orders, customers tables")
        ContainerDb(pgvec, "pgvector", "Supabase Postgres + pgvector extension", "handbook_chunks table with vector embeddings")
        ContainerDb(mongo, "MongoDB", "MongoDB Atlas", "reviews, support_tickets, activity_logs collections")
    }

    System_Ext(openai, "OpenAI API")

    Rel(manager, spa, "Types question", "Browser")
    Rel(spa, api, "POST /chat {question}", "HTTP/JSON")
    Rel(api, agent, "Invokes agent with question")
    Rel(agent, tools, "Calls tools via ReAct loop")
    Rel(tools, pg, "SELECT queries", "psycopg / asyncpg")
    Rel(tools, pgvec, "Vector similarity search", "psycopg / asyncpg")
    Rel(tools, mongo, "find() queries", "pymongo")
    Rel(agent, openai, "LLM reasoning", "HTTPS")
    Rel(tools, openai, "Embedding generation", "HTTPS")
    Rel(api, spa, "{answer, tool_calls, warnings, elapsed_ms}", "HTTP/JSON")
```

---

## 3. Data Flow — Single Request Lifecycle

```mermaid
sequenceDiagram
    participant U as Store Manager
    participant FE as React Frontend
    participant API as FastAPI Server
    participant AG as ReAct Agent
    participant LLM as GPT-4o-mini
    participant TL as Tool Layer
    participant DB as Data Store

    U->>FE: Types question + clicks "Ask"
    FE->>API: POST /chat {"question": "..."}
    
    Note over API: Start timer, validate request

    API->>AG: invoke({"input": question})
    
    loop ReAct Loop (max 5 iterations)
        AG->>LLM: System prompt + question + scratchpad
        LLM-->>AG: Action: tool_name, Action Input: {args}
        AG->>TL: Call tool with validated args
        
        alt sql_query
            TL->>TL: Validate SQL (no writes, no multi-stmt)
            TL->>DB: Execute SELECT with 5s timeout
            DB-->>TL: Result rows (max 50)
        else mongo_query
            TL->>TL: Validate collection whitelist + filter safety
            TL->>DB: collection.find(filter, limit)
            DB-->>TL: Documents (max 20)
        else handbook_search
            TL->>LLM: Embed query via text-embedding-3-small
            LLM-->>TL: Query embedding vector
            TL->>DB: pgvector cosine similarity search
            DB-->>TL: Top-k chunks with sections
        end
        
        TL-->>AG: Tool result (always string, never crashes)
        AG->>AG: Append observation to scratchpad
    end
    
    AG->>LLM: Final reasoning with all observations
    LLM-->>AG: Final Answer: "..."
    AG-->>API: AgentFinish with output + intermediate_steps
    
    Note over API: Stop timer, extract tool_calls, build response

    API-->>FE: {answer, tool_calls, warnings, elapsed_ms}
    FE-->>U: Render answer + expandable tool trace
```

---

## 4. Deployment Topology

```mermaid
graph TB
    subgraph "Developer Machine / CI"
        FE["Vite Dev Server<br/>localhost:5173"]
        BE["Uvicorn + FastAPI<br/>localhost:8000"]
    end

    subgraph "Cloud Services"
        OPENAI["OpenAI API<br/>api.openai.com"]
        SUPA["Supabase Postgres<br/>*.supabase.co:5432<br/>+ pgvector extension"]
        MONGO["MongoDB Atlas<br/>*.mongodb.net:27017"]
    end

    FE -->|"POST /chat"| BE
    BE -->|"LLM + Embeddings"| OPENAI
    BE -->|"SQL + Vector"| SUPA
    BE -->|"Document queries"| MONGO

    style FE fill:#3b82f6,color:#fff
    style BE fill:#10b981,color:#fff
    style OPENAI fill:#6366f1,color:#fff
    style SUPA fill:#f59e0b,color:#fff
    style MONGO fill:#22c55e,color:#fff
```

---

## 5. Security Boundary Map

```mermaid
graph LR
    subgraph "Trust Zone: Browser"
        USER["User Input"]
    end

    subgraph "Trust Zone: Backend"
        VALIDATE["Input Validation<br/>(Pydantic)"]
        AGENT["ReAct Agent<br/>(LangChain)"]
        TOOLS["Tool Layer<br/>(Sandboxed)"]
    end

    subgraph "Trust Zone: External"
        PG["Postgres<br/>(Read-Only Role)"]
        MG["MongoDB<br/>(Read-Only Role)"]
        OAI["OpenAI API"]
    end

    USER -->|"POST /chat"| VALIDATE
    VALIDATE -->|"Sanitized question"| AGENT
    AGENT -->|"Tool call"| TOOLS

    TOOLS -->|"Validated SELECT only"| PG
    TOOLS -->|"Whitelisted collection + safe filter"| MG
    TOOLS -->|"Embedding request"| OAI

    style USER fill:#ef4444,color:#fff
    style VALIDATE fill:#f59e0b,color:#fff
    style AGENT fill:#10b981,color:#fff
    style TOOLS fill:#10b981,color:#fff
    style PG fill:#3b82f6,color:#fff
    style MG fill:#3b82f6,color:#fff
    style OAI fill:#6366f1,color:#fff
```

---

## 6. Project Directory Structure

```
MultiDBAgent_class5_hw2_ManojKumarY/
│
├── SPEC.md                          # Specification (committed first)
├── README.md                        # Setup, architecture, decisions, findings
├── .env.example                     # Required environment variables (no secrets)
├── pyproject.toml                   # Python project config (uv)
│
├── docs/
│   ├── ARCHITECTURE.md              # This file — system architecture
│   ├── HLD.md                       # High-Level Design
│   └── LLD.md                       # Low-Level Design
│
├── backend/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── agent.py
│   └── tools/
│       ├── sql_tool.py
│       ├── mongo_tool.py
│       └── rag_tool.py
├── scripts/
│   ├── seed_postgres.py
│   ├── seed_mongo.py
│   └── index_policies.py
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
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── chat.ts              # POST /chat API client
│       ├── components/
│       │   ├── ChatWindow.tsx
│       │   ├── MessageBubble.tsx
│       │   ├── ToolTrace.tsx         # Expandable tool-call trace panel
│       │   ├── InputBar.tsx
│       │   └── WarningBanner.tsx
│       └── types/
│           └── index.ts             # TypeScript interfaces matching API contract
│
└── tests/
    ├── conftest.py                  # Shared fixtures (DB connections, mock LLM)
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

---

## 7. Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent never touches DB directly | Tools are the only data interface | Enforces the ReAct pattern. Agent receives string results, never connection objects. Prevents prompt-injection from escalating to data-level access. |
| Tools always return strings | Even on error, tools return a descriptive string | Prevents the ReAct loop from crashing on exceptions. The agent can reason about errors gracefully. |
| Read-only database roles | Postgres and MongoDB connections use read-only credentials | Defense-in-depth. Even if SQL validation is bypassed, the DB role cannot write. |
| pgvector in Supabase Postgres | Handbook embeddings stored alongside transactional data | Single Postgres instance simplifies ops. pgvector extension is natively supported on Supabase. No separate vector DB needed for this scale. |
| Single `/chat` endpoint | No REST resources, no CRUD | The agent is the API. One question in, one grounded answer out. Matches the assignment requirement and keeps the interface simple. |
| Pydantic everywhere | Tool args, API request/response, config | Type safety from the HTTP boundary to the tool invocation. Validation errors surface before any database call. |

---

*This document is the bird's-eye view. For component-level design, see [HLD.md](./HLD.md). For implementation-level contracts, see [LLD.md](./LLD.md).*
