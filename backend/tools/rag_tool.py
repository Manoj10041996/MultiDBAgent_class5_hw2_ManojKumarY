"""
rag_tool.py — Semantic vector search over StockPulse policy documents.

Embeddings: SentenceTransformers all-MiniLM-L6-v2 (local, 384-dim, no API key).
Vector store: Postgres + pgvector extension (policy_chunks table).

The SentenceTransformer model is loaded once at module import time (singleton).
It runs entirely locally — no network call, no API key required for embeddings.
"""

import json

import psycopg2
import psycopg2.extras
from langchain_core.tools import tool
from sentence_transformers import SentenceTransformer

from backend.config import settings

# ---------------------------------------------------------------------------
# Embedding model — loaded once at startup (local, CPU-friendly)
# ---------------------------------------------------------------------------

_embedding_model = SentenceTransformer(settings.embedding_model_name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _embed(text: str) -> list[float]:
    """
    Embed a text string using the local SentenceTransformer model.
    Returns a list of floats (384-dim for all-MiniLM-L6-v2).
    """
    embedding = _embedding_model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def _vector_search(embedding: list[float], k: int) -> list[dict]:
    """
    Run cosine similarity search against the policy_chunks pgvector table.
    Returns list of dicts: {section, chunk, similarity}.
    """
    # pgvector cosine distance operator: <=>
    # similarity = 1 - distance
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

    Embeddings are generated locally using all-MiniLM-L6-v2 (SentenceTransformers).
    Results are ranked by cosine similarity against the pgvector policy index.

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
        embedding = _embed(query)
    except Exception as exc:
        return f"SEARCH ERROR: embedding failed — {str(exc)}"

    try:
        results = _vector_search(embedding, k)
    except Exception as exc:
        return f"SEARCH ERROR: vector search failed — {str(exc)}"

    # Filter below similarity threshold to avoid hallucination-inducing noise
    relevant = [
        {"section": r["section"], "chunk": r["chunk"]}
        for r in results
        if r.get("similarity", 0) >= settings.rag_similarity_threshold
    ]

    return json.dumps(relevant, default=str)
