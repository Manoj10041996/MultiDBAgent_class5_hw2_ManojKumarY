"""
main.py — FastAPI application entry point for StockPulse Intelligence Agent.

Single endpoint: POST /chat
Accepts a question, runs the ReAct agent, returns answer + tool trace.
"""

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agent import agent_executor

# ---------------------------------------------------------------------------
# Pydantic models — API contract
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000,
                          description="Natural language question from the store manager")


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
    # agent_executor is a module-level singleton — already initialised on import
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
# Helper: extract tool-call trace from LangChain intermediate steps
# ---------------------------------------------------------------------------


def _extract_tool_calls(intermediate_steps: list) -> tuple[list[ToolCallRecord], list[str]]:
    """
    Parses LangChain's intermediate_steps list into ToolCallRecord objects.

    intermediate_steps is a list of (AgentAction, observation_str) tuples.
    """
    records: list[ToolCallRecord] = []
    warnings: list[str] = []

    for action, observation in intermediate_steps:
        tool_name = action.tool
        tool_input = action.tool_input
        result_str = str(observation)

        records.append(
            ToolCallRecord(
                tool=tool_name,
                args=tool_input,
                result=result_str,
            )
        )

        # Surface soft errors as warnings
        if result_str.startswith("REFUSED:"):
            warnings.append(f"[{tool_name}] {result_str}")
        elif result_str.startswith("SQL ERROR:") or result_str.startswith("MONGO ERROR:") or result_str.startswith("SEARCH ERROR:"):
            warnings.append(f"[{tool_name}] {result_str}")
        elif result_str in ("[]", "null", ""):
            warnings.append(f"[{tool_name}] returned no results")

    return records, warnings


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Submit a natural-language question to the StockPulse agent.

    The agent will select the appropriate tool(s), query the relevant database,
    and return a grounded answer with full tool-call traceability.
    """
    start_ms = time.time()

    try:
        result = agent_executor.invoke({"input": request.question})
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(exc)}",
        ) from exc

    elapsed_ms = int((time.time() - start_ms) * 1000)

    answer: str = result.get("output", "No answer produced.")
    intermediate_steps: list = result.get("intermediate_steps", [])

    tool_calls, warnings = _extract_tool_calls(intermediate_steps)

    return ChatResponse(
        answer=answer,
        tool_calls=tool_calls,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
    )


@app.get("/health")
async def health():
    """Health check endpoint for Docker/CI."""
    return {"status": "ok"}
