"""
index_policies.py — Chunks policy documents and loads embeddings into Postgres pgvector.

This script:
1. Reads Markdown policy files from the policies/ directory.
2. Splits each file into ~300-token chunks with 50-token overlap.
3. Embeds each chunk using OpenAI text-embedding-3-small.
4. Upserts into the policy_chunks table in Postgres.

Usage:
    uv run python scripts/index_policies.py

Requires OPENAI_API_KEY and POSTGRES_URL in environment / .env.
"""

import os
import re
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
POSTGRES_URL   = os.environ["POSTGRES_URL"]
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
POLICIES_DIR   = Path(__file__).parent.parent / "policies"

# Approximate token counts using word-based splitting (good enough for chunking)
CHUNK_SIZE_WORDS   = 200   # ~300 tokens at ~1.5 words/token
OVERLAP_WORDS      = 35    # ~50-token overlap


# ---------------------------------------------------------------------------
# DDL for policy_chunks table
# ---------------------------------------------------------------------------

CREATE_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_chunks (
    id          SERIAL PRIMARY KEY,
    document    TEXT    NOT NULL,
    section     TEXT    NOT NULL,
    chunk       TEXT    NOT NULL,
    embedding   vector(1536) NOT NULL
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
    # parts[0] is any text before the first ##
    if parts[0].strip():
        sections.append((doc_name, parts[0].strip()))

    # parts[1], parts[2], parts[3], parts[4]... = heading, body, heading, body...
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
# Embedding helper (batch to avoid rate limits)
# ---------------------------------------------------------------------------

def _embed_batch(texts: list[str], client: OpenAI) -> list[list[float]]:
    response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    return [d.embedding for d in response.data]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def index_policies():
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    print("Connecting to Postgres…")
    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating policy_chunks table…")
    cur.execute(CREATE_TABLE_SQL)
    cur.execute("TRUNCATE TABLE policy_chunks RESTART IDENTITY")

    policy_files = list(POLICIES_DIR.glob("*.md"))
    if not policy_files:
        print(f"⚠️  No .md files found in {POLICIES_DIR}")
        sys.exit(1)

    for policy_file in policy_files:
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

        # Embed in batches of 20
        BATCH = 20
        for i in range(0, len(all_rows), BATCH):
            batch = all_rows[i : i + BATCH]
            texts = [row[2] for row in batch]
            embeddings = _embed_batch(texts, openai_client)
            for (doc, section, chunk), emb in zip(batch, embeddings):
                cur.execute(
                    """
                    INSERT INTO policy_chunks (document, section, chunk, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    """,
                    (doc, section, chunk, emb),
                )
            print(f"  Batch {i // BATCH + 1}: inserted {len(batch)} chunks")

    cur.close()
    conn.close()
    print("\n✅  Policy index complete.")


if __name__ == "__main__":
    index_policies()
