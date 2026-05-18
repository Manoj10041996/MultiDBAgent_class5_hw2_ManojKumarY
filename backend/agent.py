"""
agent.py — LangChain v1 ReAct agent factory for StockPulse.

The agent is the orchestrator. It receives a natural-language question,
decides which tool(s) to call, observes the results, and synthesises a
final grounded answer. It NEVER reads from databases directly.

Key design decisions:
  - temperature=0 for deterministic, grounded tool-calling behaviour.
  - return_intermediate_steps=True so the /chat endpoint can extract the
    full tool-call trace for the frontend.
  - handle_parsing_errors=True prevents LLM formatting mistakes from
    crashing the agent loop.
  - max_iterations=settings.agent_max_iterations (default 5).
"""

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from backend.config import settings
from backend.tools.mongo_tool import mongo_query
from backend.tools.rag_tool import handbook_search
from backend.tools.sql_tool import sql_query

# ---------------------------------------------------------------------------
# System prompt — defines routing rules and hard constraints
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the StockPulse Store Intelligence Agent — an internal tool \
for store operations managers at StockPulse e-commerce.

You have access to three tools. Use them according to these rules:

TOOL SELECTION:
- sql_query: use for any question about products, orders, sales, revenue, stock levels, \
customers, quantities, dates, totals, rankings, or any structured transactional data.

- mongo_query: use for any question about customer reviews, star ratings, complaints, \
support tickets, refund requests, return complaints, or user activity and behaviour logs.

- handbook_search: use for any question about store policies, return rules, shipping terms, \
discount eligibility, promotion conditions, or any procedural or compliance question.

HARD RULES:
- Never answer from memory or training data. Always use a tool.
- Do not call a tool if a previous tool result already answers the question.
- If a tool returns an error or empty result, report it honestly.
- Cite exact numbers and field values returned by the tools.
- Answer in one short paragraph.

You have access to the following tools:
{tools}

Use the following format EXACTLY:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat up to {max_iterations} times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""

# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

_TOOLS = [sql_query, mongo_query, handbook_search]


def build_agent_executor() -> AgentExecutor:
    """
    Constructs and returns a configured LangChain AgentExecutor.
    Called once at startup and cached — do not call per-request.
    """
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )

    prompt = PromptTemplate.from_template(SYSTEM_PROMPT)
    prompt = prompt.partial(max_iterations=settings.agent_max_iterations)

    agent = create_react_agent(llm=llm, tools=_TOOLS, prompt=prompt)

    return AgentExecutor(
        agent=agent,
        tools=_TOOLS,
        max_iterations=settings.agent_max_iterations,
        return_intermediate_steps=True,   # Required: powers the tool-trace UI
        handle_parsing_errors=True,        # Prevents LLM formatting mistakes from crashing
        verbose=True,                      # Logs reasoning to stdout — useful during dev
    )


# Module-level singleton — imported by main.py
agent_executor: AgentExecutor = build_agent_executor()
