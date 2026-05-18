"""
rag_tool.py — Semantic vector search over StockPulse policy documents.

Uses OpenAI text-embedding-3-small to embed the query, then runs a
pgvector cosine similarity search against the policy_chunks table.

Returns the top-k most relevant policy chunks with their section labels.
Always returns a plain string — the ReAct loop never crashes.
"""

import json

import psycopg2
import psycopg2.extras
from langchain_core.tools import tool
from openai import OpenAI

from backend.config import settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _embed(text: str) -> list[float]:
    """Call OpenAI Embeddings API and return the embedding vector."""
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        input=text,
        model=settings.embedding_model,
    )
    return response.data[0].embedding


def _vector_search(embedding: list[float], k: int) -> list[dict]:
    """
    Run a cosine similarity search against the policy_chunks pgvector table.
    Returns list of dicts: {section, chunk, similarity}.
    """
    # pgvector cosine distance operator: <=>
    # similarity = 1 - distance (higher is more similar)
    query = f"""
        SELECT
            section,
            chunk,
            1 - (embedding <=> %s::vector) AS similarity
        FROM {settings.policy_chunks_table}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    conn = None
    try:
        conn = psycopg2.connect(
            settings.postgres_url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        with conn.cursor() as cur:
            cur.execute(query, (embedding, embedding, k))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool
def handbook_search(query: str, k: int = 3) -> str:
    """
    Semantic search over StockPulse internal policy documents.

    Use this tool for questions about store policies, return rules, shipping
    terms, discount eligibility, promotion conditions, or any procedural or
    compliance question.

    Args:
        query: The natural language question to search against policy documents.
        k: Number of relevant chunks to return (default 3, max 5).

    Returns:
        A JSON list of {section, chunk} dicts, or a SEARCH ERROR string.
        Returns an empty list [] if no sufficiently relevant chunks are found.
    """
    if not query or not query.strip():
        return "[]"

    # Cap k
    k = min(max(1, k), settings.rag_max_k)

    try:
        # 1. Embed the query
        embedding = _embed(query)
    except Exception as exc:
        return f"SEARCH ERROR: embedding failed — {str(exc)}"

    try:
        # 2. Vector search
        results = _vector_search(embedding, k)
    except Exception as exc:
        return f"SEARCH ERROR: vector search failed — {str(exc)}"

    # 3. Filter below similarity threshold to avoid hallucination-inducing noise
    relevant = [
        {"section": r["section"], "chunk": r["chunk"]}
        for r in results
        if r.get("similarity", 0) >= settings.rag_similarity_threshold
    ]

    return json.dumps(relevant, default=str)
