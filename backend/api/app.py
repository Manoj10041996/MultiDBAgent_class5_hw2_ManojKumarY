"""FastAPI app wiring for StockPulse Intelligence Agent."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.agent import agent
from backend.api.message_parser import extract_tool_calls, get_final_answer, normalize_answer_text
from backend.api.schemas import ChatRequest, ChatResponse
from backend.config import settings


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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    start_ms = time.time()

    try:
        result = agent.invoke(
            {"messages": [("user", request.question)]},
            config={"recursion_limit": settings.agent_max_iterations * 2 + 2},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(exc)}") from exc

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

