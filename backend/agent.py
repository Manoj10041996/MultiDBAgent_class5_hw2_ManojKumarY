"""
agent.py — LangChain v1 ReAct agent using Groq API.

LLM:   Groq (openai/gpt-oss-120b) via langchain-groq ChatGroq
Tools: sql_query, mongo_query, handbook_search

The agent NEVER reads from databases directly.
Every data access goes through a typed, sandboxed tool.
"""

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq

from backend.config import settings
from backend.tools.mongo_tool import mongo_query
from backend.tools.rag_tool import handbook_search
from backend.tools.sql_tool import sql_query

# ---------------------------------------------------------------------------
# System prompt — routing rules and hard constraints (from SPEC.md §3)
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
    Constructs and returns a configured LangChain AgentExecutor backed by Groq.
    Called once at startup — module-level singleton.
    """
    llm = ChatGroq(
        model=settings.llm_model,
        temperature=0,
        groq_api_key=settings.groq_api_key,
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
        verbose=True,
    )


# Module-level singleton — imported by main.py
agent_executor: AgentExecutor = build_agent_executor()
