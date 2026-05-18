"""
main.py — FastAPI application entry point for StockPulse Intelligence Agent.

Single endpoint: POST /chat
Accepts a question, runs the ReAct agent, returns answer + tool trace.

The agent (langgraph.prebuilt.create_react_agent) returns a state dict with a
'messages' list instead of the old 'intermediate_steps'. This file parses that
messages list to reconstruct the full tool-call trace required by the SPEC.

Message types in the result:
  HumanMessage  — the original question
  AIMessage     — LLM reasoning step; .tool_calls list signals which tools to call
  ToolMessage   — result of one tool call; .tool_call_id links back to AIMessage
  AIMessage     — final answer (last AIMessage, no .tool_calls)
"""

import json
import re
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field

from backend.agent import agent
from backend.config import settings

# ---------------------------------------------------------------------------
# Pydantic models — API contract
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str = Field(
        ..., min_length=1, max_length=1000,
        description="Natural language question from the store manager",
    )


class ToolCallRecord(BaseModel):
    tool: str = Field(..., description="Name of the tool that was called")
    args: Any = Field(..., description="Arguments passed to the tool")
    result: str = Field(..., description="Raw string result returned by the tool")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Agent's final natural-language answer")
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list,
        description="Ordered list of every tool invocation in this turn",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Guardrail triggers, empty results, or soft errors",
    )
    elapsed_ms: int = Field(..., description="Wall-clock time from request to response (ms)")


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # agent is a module-level singleton — already initialised on import
    yield


app = FastAPI(
    title="StockPulse Store Intelligence Agent",
    description=(
        "Conversational AI agent for e-commerce store operations. "
        "Queries Postgres, MongoDB, and a pgvector policy handbook."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the Vite dev server during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helper: extract tool-call trace from LangGraph messages list
# ---------------------------------------------------------------------------


def _extract_tool_calls(messages: list) -> tuple[list[ToolCallRecord], list[str]]:
    """
    Parses the LangGraph messages list into ToolCallRecord objects.

    The new create_react_agent returns a 'messages' list where:
      - AIMessage with .tool_calls  →  the LLM decided to call a tool
      - ToolMessage                 →  the actual tool result (.tool_call_id links back)

    We build a lookup of tool_call_id → ToolMessage, then walk AIMessages
    to reconstruct each (tool_name, args, result) triple in call order.
    """
    # Index all ToolMessages by their tool_call_id for O(1) lookup
    tool_results: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_results[msg.tool_call_id] = str(msg.content)

    records: list[ToolCallRecord] = []
    provisional_warnings: list[tuple[int, str, str]] = []
    success_indices_by_tool: dict[str, list[int]] = {}

    def _warning_message(tool_name: str, result_str: str) -> str | None:
        if result_str.startswith("REFUSED:"):
            return f"[{tool_name}] {result_str}"
        if any(result_str.startswith(p) for p in ("SQL ERROR:", "MONGO ERROR:", "SEARCH ERROR:")):
            return f"[{tool_name}] {result_str}"
        if result_str in ("[]", "null", ""):
            return f"[{tool_name}] returned no results"
        return None

    def _is_successful_result(result_str: str) -> bool:
        if result_str in ("", "[]", "null", "(no result captured)"):
            return False
        if result_str.startswith("REFUSED:"):
            return False
        if any(result_str.startswith(p) for p in ("SQL ERROR:", "MONGO ERROR:", "SEARCH ERROR:")):
            return False
        return True

    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        if not msg.tool_calls:
            continue

        for tc in msg.tool_calls:
            tool_name = tc["name"]
            tool_args = tc.get("args", {})
            call_id   = tc.get("id", "")
            result_str = tool_results.get(call_id, "(no result captured)")

            records.append(ToolCallRecord(
                tool=tool_name,
                args=tool_args,
                result=result_str,
            ))

            record_index = len(records) - 1
            warning = _warning_message(tool_name, result_str)
            if warning:
                provisional_warnings.append((record_index, tool_name, warning))
            elif _is_successful_result(result_str):
                success_indices_by_tool.setdefault(tool_name, []).append(record_index)

    final_warnings: list[str] = []
    for warning_index, tool_name, warning_message in provisional_warnings:
        success_indices = success_indices_by_tool.get(tool_name, [])
        recovered_later = any(success_index > warning_index for success_index in success_indices)
        if not recovered_later:
            final_warnings.append(warning_message)

    return records, final_warnings


def _get_final_answer(messages: list) -> str:
    """
    Returns the content of the last AIMessage that has no tool_calls
    (i.e., the final grounded answer, not a reasoning step).
    """
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content
            if isinstance(content, str):
                return content
            # Some LLMs return a list of content blocks
            if isinstance(content, list):
                return " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
    return "No answer produced."


def _normalize_answer_text(answer: str) -> str:
    """
    Converts markdown-like list formatting into plain chatbot text.
    """
    cleaned_lines: list[str] = []
    for raw_line in answer.splitlines():
        line = re.sub(r"^\s*[*-]\s+", "", raw_line).strip()
        if line:
            cleaned_lines.append(line)
    if not cleaned_lines:
        return answer.strip()
    return " ".join(cleaned_lines)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Submit a natural-language question to the StockPulse agent.

    The agent selects the appropriate tool(s), queries the relevant database,
    and returns a grounded answer with full tool-call traceability.
    """
    start_ms = time.time()

    try:
        result = agent.invoke(
            {"messages": [("user", request.question)]},
            config={"recursion_limit": settings.agent_max_iterations * 2 + 2},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(exc)}",
        ) from exc

    elapsed_ms = int((time.time() - start_ms) * 1000)

    messages = result.get("messages", [])
    answer = _normalize_answer_text(_get_final_answer(messages))
    tool_calls, api_warnings = _extract_tool_calls(messages)

    return ChatResponse(
        answer=answer,
        tool_calls=tool_calls,
        warnings=api_warnings,
        elapsed_ms=elapsed_ms,
    )


@app.get("/health")
async def health():
    """Health check endpoint for Docker/CI."""
    return {"status": "ok"}
