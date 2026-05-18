"""FastAPI app wiring for StockPulse Intelligence Agent."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.agent import agent
from backend.api.message_parser import extract_tool_calls, get_final_answer, normalize_answer_text
from backend.api.schemas import ChatRequest, ChatResponse
from backend.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Agent is a module-level singleton already initialized on import.
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


def _error_chain_message(exc: Exception) -> str:
    messages: list[str] = []
    current: Exception | None = exc
    while current is not None:
        text = str(current).strip()
        if text:
            messages.append(text)
        current = current.__cause__ if isinstance(current.__cause__, Exception) else None
    return " | ".join(messages) if messages else exc.__class__.__name__


def _build_agent_error_detail(exc: Exception) -> str:
    chain = _error_chain_message(exc)
    lowered = chain.lower()

    if "connection error" in lowered or "timed out" in lowered or "dns" in lowered:
        return (
            "Agent error: LLM provider connection failed. "
            "Check GROQ_API_KEY, outbound internet access, and provider availability. "
            f"Details: {chain}"
        )

    return f"Agent error: {chain}"


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    start_ms = time.time()

    try:
        result = agent.invoke(
            {"messages": [("user", request.question)]},
            config={"recursion_limit": settings.agent_max_iterations * 2 + 2},
        )
    except Exception as exc:
        detail = _build_agent_error_detail(exc)
        logger.exception("Chat request failed: %s", detail)
        raise HTTPException(status_code=500, detail=detail) from exc

    elapsed_ms = int((time.time() - start_ms) * 1000)
    messages = result.get("messages", [])
    answer = normalize_answer_text(get_final_answer(messages))
    tool_calls, warnings = extract_tool_calls(messages)

    return ChatResponse(
        answer=answer,
        tool_calls=tool_calls,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/dependencies")
async def dependency_health():
    checks = {
        "groq_api_key_configured": bool(settings.groq_api_key),
        "postgres_url_configured": bool(settings.postgres_url),
        "mongo_url_configured": bool(settings.mongo_url),
        "llm_model": settings.llm_model,
        "embedding_model_name": settings.embedding_model_name,
    }
    all_required = (
        checks["groq_api_key_configured"]
        and checks["postgres_url_configured"]
        and checks["mongo_url_configured"]
    )

    return {
        "status": "ok" if all_required else "degraded",
        "checks": checks,
        "note": (
            "This endpoint validates configuration presence only. "
            "Use POST /chat to validate live provider/database connectivity."
        ),
    }
