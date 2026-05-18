"""
index_policies.py — Chunks policy documents and loads embeddings into Postgres pgvector.

Embeddings: SentenceTransformers all-MiniLM-L6-v2 (local, 384-dim, no API key needed).
Vector column: vector(384) — matches all-MiniLM-L6-v2 output dimension.

This script:
1. Reads Markdown policy files from the policies/ directory.
2. Splits each file into ~200-word chunks with 35-word overlap.
3. Embeds each chunk locally using all-MiniLM-L6-v2.
4. Upserts into the policy_chunks table in Postgres.

Usage:
    uv run python scripts/index_policies.py

Requires POSTGRES_URL in environment / .env.
Does NOT require any API key — embeddings run fully locally.
"""

import os
import re
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

POSTGRES_URL        = os.environ["POSTGRES_URL"]
EMBEDDING_MODEL     = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
EMBEDDING_DIM       = 384   # all-MiniLM-L6-v2 fixed output dimension
POLICIES_DIR        = Path(__file__).parent.parent / "policies"

CHUNK_SIZE_WORDS    = 200   # ~300 tokens at ~1.5 words/token
OVERLAP_WORDS       = 35    # ~50-token overlap


# ---------------------------------------------------------------------------
# DDL — policy_chunks table with 384-dim vector column
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_chunks (
    id          SERIAL PRIMARY KEY,
    document    TEXT    NOT NULL,
    section     TEXT    NOT NULL,
    chunk       TEXT    NOT NULL,
    embedding   vector({EMBEDDING_DIM}) NOT NULL
);

CREATE INDEX IF NOT EXISTS policy_chunks_embedding_idx
    ON policy_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
"""


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

def _parse_sections(text: str, doc_name: str) -> list[tuple[str, str]]:
    """
    Splits a Markdown document into (section_title, section_text) pairs.
    Sections are delimited by ## headings.
    """
    parts = re.split(r"(?m)^(##\s+.+)$", text)
    if not parts:
        return [(doc_name, text)]

    sections = []
    if parts[0].strip():
        sections.append((doc_name, parts[0].strip()))

    for i in range(1, len(parts), 2):
        heading = parts[i].replace("##", "").strip()
        body    = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if body:
            sections.append((heading, body))

    return sections


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Sliding-window word-based chunking with overlap."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def index_policies():
    print(f"Loading embedding model: {EMBEDDING_MODEL} …")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"  Model loaded. Output dim: {model.get_sentence_embedding_dimension()}")

    print("Connecting to Postgres…")
    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating policy_chunks table (384-dim vectors)…")
    cur.execute(CREATE_TABLE_SQL)
    cur.execute("TRUNCATE TABLE policy_chunks RESTART IDENTITY")

    policy_files = list(POLICIES_DIR.glob("*.md"))
    if not policy_files:
        print(f"⚠️  No .md files found in {POLICIES_DIR}")
        sys.exit(1)

    for policy_file in sorted(policy_files):
        doc_name = policy_file.stem.replace("_", " ").title()
        print(f"\nIndexing: {policy_file.name} → document='{doc_name}'")

        text = policy_file.read_text(encoding="utf-8")
        sections = _parse_sections(text, doc_name)

        all_rows = []  # (doc_name, section, chunk)
        for section_title, section_body in sections:
            chunks = _chunk_text(section_body, CHUNK_SIZE_WORDS, OVERLAP_WORDS)
            for chunk in chunks:
                if chunk.strip():
                    all_rows.append((doc_name, section_title, chunk))

        print(f"  {len(sections)} sections → {len(all_rows)} chunks")

        # Embed all chunks in one batch (SentenceTransformer handles batching internally)
        texts = [row[2] for row in all_rows]
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

        for (doc, section, chunk), emb in zip(all_rows, embeddings):
            cur.execute(
                """
                INSERT INTO policy_chunks (document, section, chunk, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                (doc, section, chunk, emb.tolist()),
            )

        print(f"  ✓ {len(all_rows)} chunks indexed for '{doc_name}'")

    cur.close()
    conn.close()
    print("\n✅  Policy index complete.")


if __name__ == "__main__":
    index_policies()
