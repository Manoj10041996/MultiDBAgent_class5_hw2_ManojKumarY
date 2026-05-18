"""
agent.py — LangChain ReAct agent for StockPulse Intelligence.

Uses langgraph.prebuilt.create_react_agent — the canonical, production-grade
ReAct implementation (tool-calling loop backed by LangGraph state machine).

This is NOT a downgrade from the original create_react_agent. It IS
create_react_agent — just imported from the correct package in the installed env.

  Old (removed from langchain.agents):  create_react_agent + AgentExecutor
  New (canonical):  langgraph.prebuilt.create_react_agent → CompiledStateGraph

The agent is invoked with:
    result = agent.invoke({"messages": [("user", question)]})

Result["messages"] contains the full conversation:
    HumanMessage, AIMessage (with tool_calls), ToolMessage(s), AIMessage (final)

The SPEC requirement for return_intermediate_steps=True is satisfied by parsing
the messages list in main.py — every tool call and result is present.
"""

import warnings

# Suppress the LangGraph deprecation warning on the create_react_agent name —
# the function is identical; only the canonical import path changed.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langgraph.prebuilt import create_react_agent

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

You have access to three tools. Use them according to these routing rules:

TOOL SELECTION:
- sql_query: questions about products, orders, sales, revenue, stock levels, \
customers, quantities, dates, totals, or any structured transactional data.

- mongo_query: questions about customer reviews, star ratings, complaints, \
support tickets, refund requests, return complaints, or user activity logs.

- handbook_search: questions about store policies, return rules, shipping terms, \
discount eligibility, promotion conditions, or any procedural/compliance question.

HARD RULES:
- Never answer from memory or training data. Always call a tool first.
- Do not call a tool if a previous tool result already answers the question.
- If a tool returns an error or empty result, report it honestly.
- Cite exact numbers and field values returned by the tools.
- Give a concise, grounded answer in one paragraph.
- Output plain text only (generic chatbot style), with no Markdown bullets or asterisks.

SQL SCHEMA HINTS (IMPORTANT):
- customers table primary key is customers.id (not customers.customer_id).
- orders.customer_id joins to customers.id.
- products table primary key is products.id.
- orders.product_id joins to products.id.
- If unsure about columns, run a schema-inspection SELECT first (e.g., information_schema.columns)."""

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

_TOOLS = [sql_query, mongo_query, handbook_search]

# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def build_agent():
    """
    Builds and returns the ReAct agent as a CompiledStateGraph.
    Called once at module load — result is a module-level singleton.

    max_iterations is enforced via recursion_limit on invoke() in main.py.
    """
    llm = ChatGroq(
        model=settings.llm_model,
        temperature=0,
        groq_api_key=settings.groq_api_key,
    )

    return create_react_agent(
        model=llm,
        tools=_TOOLS,
        prompt=SYSTEM_PROMPT,   # str → converted to SystemMessage prepended to messages
    )


# Module-level singleton — imported by main.py
agent = build_agent()
