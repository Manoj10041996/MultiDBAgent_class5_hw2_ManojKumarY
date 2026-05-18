# Low-Level Design (LLD) — StockPulse Agent

This Low-Level Design maps the High-Level Design to exact code modules, class structures, Pydantic models, and execution flows required to build the StockPulse Intelligence Agent.

---

## 1. API Layer (`backend/main.py`)

### 1.1 Data Models (Pydantic)
The system relies on strong typing for all HTTP boundaries.

```python
class ChatRequest(BaseModel):
    question: str = Field(..., max_length=500)

class ToolCallRecord(BaseModel):
    tool: str
    args: dict
    result: str

class ChatResponse(BaseModel):
    answer: str
    tool_calls: List[ToolCallRecord]
    warnings: List[str]
    elapsed_ms: int
```

### 1.2 Endpoint Definition
```python
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    # 1. Start timer
    # 2. Call run_agent(request.question)
    # 3. Catch exceptions -> 500 error
    # 4. Extract LangChain intermediate_steps into ToolCallRecords
    # 5. Stop timer
    # 6. Return ChatResponse
```

---

## 2. Tool Implementation Details (`backend/tools/`)

All tools are decorated with LangChain's `@tool` to auto-generate JSON schemas for the LLM.

### 2.1 SQL Tool (`sql_tool.py`)
```python
@tool
def sql_query(sql: str) -> str:
    """Execute read-only SELECT against Postgres."""
```
**Validation Logic:**
1. Check for dangerous keywords: `sql.upper()` against `["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]`. Return `REFUSED` string if found.
2. Check for multiple statements: `if ";" in sql.strip(";"): return "REFUSED"`
3. Check starting keyword: Must start with `SELECT` or `WITH`.
4. Inject Limit: If `"LIMIT"` not in `sql.upper()` and no `GROUP BY`/aggregate, append ` LIMIT 50`.
**Execution:**
Wrap in `try/except psycopg.Error`. On catch, return `"SQL ERROR: " + str(e)`. Set `options="-c statement_timeout=5000"`.
**Formatting:**
Fetch rows as dictionaries. Return `json.dumps(rows, default=str)`.

### 2.2 MongoDB Tool (`mongo_tool.py`)
```python
@tool
def mongo_query(collection: str, filter: dict, limit: int = 10) -> str:
    """Query MongoDB Atlas collections."""
```
**Validation Logic:**
1. Whitelist: `if collection not in ["reviews", "support_tickets", "activity_logs"]: return "REFUSED"`
2. Filter Safety: Iterate dictionary keys recursively. `if key.startswith("$where") or key == "$function": return "REFUSED"`
3. Limit enforcement: `limit = min(limit, 20)`
**Execution:**
`db[collection].find(filter).limit(limit)`
**Formatting:**
Convert `ObjectId` and `datetime` to strings. Return `json.dumps(docs)`.

### 2.3 RAG Tool (`rag_tool.py`)
```python
@tool
def handbook_search(query: str, k: int = 3) -> str:
    """Semantic vector search over policy documents."""
```
**Execution Logic:**
1. Cap `k`: `k = min(k, 5)`
2. Embed: Call `openai.embeddings.create(input=query, model="text-embedding-3-small")`.
3. Query Postgres: 
   ```sql
   SELECT section, chunk, 1 - (embedding <=> %s) as similarity 
   FROM handbook_chunks 
   ORDER BY embedding <=> %s LIMIT %s
   ```
4. If results < threshold (e.g., 0.2 similarity), return `[]` to prevent LLM hallucinations.
5. Format: Return `json.dumps([{"section": r[0], "chunk": r[1]}])`.

---

## 3. Agent Configuration (`backend/agent.py` - system prompt lives here)

### 3.1 LLM Setup
```python
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
```

### 3.2 Agent Pipeline
Using the LangChain v1 ReAct pattern:
```python
prompt = PromptTemplate.from_template(SYSTEM_PROMPT_FROM_SPEC)
tools = [sql_query, mongo_query, handbook_search]
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    max_iterations=5, 
    return_intermediate_steps=True, # Critical for trace UI
    handle_parsing_errors=True      # Prevents LLM formatting crashes
)
```

---

## 4. Frontend Component State (`frontend/src/`)

### 4.1 State Management (React)
```typescript
interface Message {
  role: 'user' | 'agent';
  content: string;
  trace?: ToolCallRecord[];
  warnings?: string[];
}

const [messages, setMessages] = useState<Message[]>([]);
const [isLoading, setIsLoading] = useState(false);
```

### 4.2 Tool Trace Rendering (`ToolTrace.tsx`)
A UI component that maps over `message.trace`.
- State: `isExpanded` (boolean).
- UI: Uses Tailwind for styling. Renders `<pre><code>` blocks for `args` and `result` to format the JSON data returned from the API, truncating string length to 500 chars to avoid UI blowouts on large responses.

---

## 5. Testing Matrices (`tests/`)

### 5.1 Unit Tests (`test_sql_tool.py`, etc.)
- Use `pytest`.
- Mock Postgres and Mongo connections using `unittest.mock.patch`.
- **SQL Matrix**: Good Query, Missing Limit, Bad Syntax, DROP Table Attempt.
- **Mongo Matrix**: Good Query, Bad Collection, Exceeding Max Limit, `$where` injection attempt.
- **Agent Matrix**: Mock LLM output generating a valid action, a malformed JSON action, and a final answer. Ensure ReAct loop handles all three.

### 5.2 E2E Tests (`test_agent_e2e.py`)
- Load environment variables from `.env.test`.
- Connect to live `TestDB` instances (Supabase and Mongo).
- Iterate over the 5 specific tests and 1 failure case defined in `SPEC.md` section 4.
- Assert `len(response.tool_calls) > 0`.
- Assert `response.tool_calls[0].tool == expected_tool`.
- Assert required fields are substring matches in `response.answer`.
