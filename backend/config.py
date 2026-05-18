"""
config.py — Pydantic Settings for StockPulse Agent.
All configuration is loaded from environment variables / .env file.
No defaults contain real secrets. See .env.example for required keys.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- OpenAI ---
    openai_api_key: str

    # --- LLM ---
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # --- Agent ---
    agent_max_iterations: int = 5

    # --- Postgres / Supabase ---
    postgres_url: str  # e.g. postgresql://user:pass@host:5432/dbname

    # --- MongoDB ---
    mongo_url: str       # e.g. mongodb+srv://user:pass@cluster.mongodb.net/
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
