"""Pydantic API contract models for the chat endpoints."""

from typing import Any

from pydantic import BaseModel, Field


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

