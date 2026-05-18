"""
config.py — Pydantic Settings for StockPulse Agent.

LLM:        Groq API (openai/gpt-oss-120b)
Embeddings: SentenceTransformers all-MiniLM-L6-v2 (local, no API key needed)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Groq API (LLM) ---
    groq_api_key: str

    # --- LLM ---
    llm_model: str = "openai/gpt-oss-120b"

    # --- Embeddings (local SentenceTransformer — no API key needed) ---
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384   # all-MiniLM-L6-v2 produces 384-dim vectors

    # --- Agent ---
    agent_max_iterations: int = 5

    # --- Postgres / Supabase ---
    postgres_url: str  # e.g. postgresql://user:pass@host:5432/dbname

    # --- MongoDB ---
    mongo_url: str        # e.g. mongodb+srv://user:pass@cluster.mongodb.net/
    mongo_db: str = "stockpulse"

    # --- Tool limits ---
    sql_row_limit: int = 50
    sql_timeout_ms: int = 5000
    mongo_doc_limit: int = 20
    rag_default_k: int = 3
    rag_max_k: int = 5
    rag_similarity_threshold: float = 0.2
    policy_chunks_table: str = "policy_chunks"


# Singleton — import this everywhere
settings = Settings()
