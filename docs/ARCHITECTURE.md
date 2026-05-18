# StockPulse Store Intelligence Agent — Architecture

> Multi-database conversational AI agent for e-commerce store operations.
> One question in → grounded answer out, with full tool-call receipts.

---

## 1. System Overview

```mermaid
graph TD
    MGR["🧑‍💼 Store Manager<br/>(Browser)"]
    FE["⚛️ React Frontend<br/>Vite · TypeScript · Tailwind<br/>localhost:5173"]
    BE["🚀 FastAPI Backend<br/>Uvicorn · Python 3.12<br/>localhost:8000"]
    AG["🤖 ReAct Agent<br/>langgraph create_react_agent<br/>ChatGroq · gpt-oss-120b"]
    SQL["🔧 sql_query<br/>Read-only SELECT<br/>LIMIT 50 · 5s timeout"]
    MDB["🔧 mongo_query<br/>Whitelisted collections<br/>Cap 20 docs"]
    RAG["🔧 handbook_search<br/>Local embeddings<br/>all-MiniLM-L6-v2"]
    PG[("🐘 Postgres<br/>products · orders<br/>customers")]
    MG[("🍃 MongoDB<br/>reviews · support_tickets<br/>activity_logs")]
    PGV[("🔍 pgvector<br/>policy_chunks<br/>vector-384")]
    GROQ["☁️ Groq API<br/>openai/gpt-oss-120b"]

    MGR -->|"question"| FE
    FE -->|"POST /chat"| BE
    BE -->|"invoke messages"| AG
    AG -->|"tool call"| SQL
    AG -->|"tool call"| MDB
    AG -->|"tool call"| RAG
    SQL -->|"SELECT"| PG
    MDB -->|"find()"| MG
    RAG -->|"cosine search"| PGV
    AG <-->|"LLM reasoning"| GROQ
    BE -->|"answer + trace"| FE
    FE -->|"rendered answer"| MGR

    classDef user fill:#6366f1,color:#fff,stroke:none
    classDef frontend fill:#3b82f6,color:#fff,stroke:none
    classDef backend fill:#10b981,color:#fff,stroke:none
    classDef tool fill:#f59e0b,color:#fff,stroke:none
    classDef db fill:#1e293b,color:#fff,stroke:#475569
    classDef cloud fill:#8b5cf6,color:#fff,stroke:none

    class MGR user
    class FE frontend
    class BE,AG backend
    class SQL,MDB,RAG tool
    class PG,MG,PGV db
    class GROQ cloud
```

---

## 2. Request Lifecycle

```mermaid
sequenceDiagram
    actor M as Manager
    participant F as Frontend
    participant A as FastAPI
    participant R as ReAct Agent
    participant G as Groq LLM
    participant T as Tool
    participant D as Database

    M->>F: Types question
    F->>A: POST /chat {"question": "..."}
    A->>R: agent.invoke(messages)

    loop ReAct loop (max 5 iterations)
        R->>G: messages + tool schemas
        G-->>R: AIMessage with tool_calls
        R->>T: Execute tool (validated args)
        T->>D: Query (read-only)
        D-->>T: Result rows / documents / chunks
        T-->>R: ToolMessage (always a string)
    end

    G-->>R: Final AIMessage (no tool_calls)
    R-->>A: {messages: [...]}
    A-->>F: {answer, tool_calls, warnings, elapsed_ms}
    F-->>M: Answer + expandable tool trace
```

---

## 3. Tool Routing

```mermaid
graph LR
    Q["❓ Question"]

    Q -->|"products · orders · sales<br/>revenue · stock · customers"| S["sql_query<br/>→ Postgres"]
    Q -->|"reviews · complaints<br/>tickets · ratings · logs"| M["mongo_query<br/>→ MongoDB"]
    Q -->|"return policy · shipping<br/>discounts · procedures"| R["handbook_search<br/>→ pgvector"]

    style Q fill:#6366f1,color:#fff,stroke:none
    style S fill:#10b981,color:#fff,stroke:none
    style M fill:#10b981,color:#fff,stroke:none
    style R fill:#10b981,color:#fff,stroke:none
```

---

## 4. Security Layers

```mermaid
graph TD
    IN["User Input<br/>POST /chat"]

    IN --> P["Pydantic Validation<br/>max_length=1000"]
    P --> AG["ReAct Agent<br/>system prompt guardrails"]
    AG --> S["sql_query<br/>🔒 11 forbidden keywords<br/>🔒 SELECT/WITH only<br/>🔒 LIMIT 50 · timeout 5s"]
    AG --> M["mongo_query<br/>🔒 3 whitelisted collections<br/>🔒 no $where / $function<br/>🔒 cap 20 docs"]
    AG --> R["handbook_search<br/>🔒 similarity threshold 0.2<br/>🔒 max k=5 chunks<br/>🔒 read-only pgvector"]
    S --> DB["Databases<br/>(read-only credentials)"]
    M --> DB
    R --> DB

    style IN fill:#ef4444,color:#fff,stroke:none
    style P fill:#f59e0b,color:#fff,stroke:none
    style AG fill:#6366f1,color:#fff,stroke:none
    style S fill:#10b981,color:#fff,stroke:none
    style M fill:#10b981,color:#fff,stroke:none
    style R fill:#10b981,color:#fff,stroke:none
    style DB fill:#1e293b,color:#fff,stroke:#475569
```

---

## 5. Project Structure

```
MultiDBAgent_class5_hw2_ManojKumarY/
│
├── SPEC.md                      # Specification (committed first)
├── README.md                    # Setup, decisions, findings
├── .env.example                 # Environment template (no secrets)
├── pyproject.toml               # Python dependencies (uv)
├── docker-compose.yml           # Postgres (pgvector) + MongoDB
│
├── docs/
│   ├── ARCHITECTURE.md          # ← this file
│   ├── HLD.md                   # Component design
│   └── LLD.md                   # Implementation contracts
│
├── backend/
│   ├── config.py                # Pydantic Settings — keys, limits
│   ├── main.py                  # FastAPI: POST /chat, GET /health
│   ├── agent.py                 # create_react_agent + ChatGroq + prompt
│   └── tools/
│       ├── sql_tool.py          # Read-only SQL with guardrails
│       ├── mongo_tool.py        # Whitelisted MongoDB queries
│       └── rag_tool.py          # SentenceTransformer + pgvector
│
├── scripts/
│   ├── seed_postgres.py         # products, customers, orders
│   ├── seed_mongo.py            # reviews, tickets, logs
│   └── index_policies.py        # chunk → embed → policy_chunks
│
├── policies/
│   ├── return_refund.md
│   ├── shipping.md
│   └── discounts.md
│
├── frontend/
│   ├── vite.config.ts           # Dev proxy /chat → :8000
│   └── src/
│       ├── App.tsx              # Chat UI + suggestions
│       ├── api/chat.ts          # POST /chat client
│       ├── components/
│       │   ├── ToolTrace.tsx    # Expandable tool-call panel
│       │   └── WarningBanner.tsx
│       └── types/index.ts       # TypeScript ↔ API contract
│
└── tests/
    ├── unit/                    # Mocked — no live DB needed
    │   ├── test_sql_tool.py     # 11 tests
    │   ├── test_mongo_tool.py   # 9 tests
    │   └── test_rag_tool.py     # 9 tests
    └── e2e/
        └── test_agent_e2e.py    # 5 acceptance + 1 failure case
```

---

## 6. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent never touches DB | Tools are the only data interface | Prevents prompt-injection from escalating to data access |
| Tools always return strings | Errors returned as strings, not raised | ReAct loop never crashes; agent reasons about failures |
| LLM: Groq | `openai/gpt-oss-120b` via `ChatGroq` | Sub-second latency; swappable via `LLM_MODEL` in `.env` |
| Embeddings: local | `all-MiniLM-L6-v2` · 384-dim · CPU | Zero API cost, zero extra dependency, 90 MB one-time download |
| pgvector in Postgres | `policy_chunks` alongside transactional tables | Single DB, single backup, no separate vector store needed |
| Single `/chat` endpoint | No REST resources | The agent IS the API — one question, one grounded answer |

---

*Component design → [HLD.md](./HLD.md) · Implementation contracts → [LLD.md](./LLD.md)*
