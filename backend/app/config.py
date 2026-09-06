"""
Central configuration, loaded entirely from environment variables (.env).

Nothing about the LLM provider or model is hardcoded anywhere else in the
codebase -- app/tools/llm_client.py reads these settings and dispatches to
the configured provider. Swapping providers/models is a config change only.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "AGFinTax Agentic Tax Coach"
    environment: str = "development"

    # --- Database ---
    # Defaults to a local SQLite file so the app runs out of the box;
    # point this at Postgres (+ pgvector) in staging/production, e.g.
    # postgresql+psycopg2://user:pass@host:5432/agfintax
    database_url: str = "sqlite:///./agfintax.db"

    # --- Redis (optional cache / rate limiting) ---
    redis_url: Optional[str] = None

    # --- LLM provider (model-agnostic, ENV-driven) ---
    # Supported today: "anthropic". Add new providers in llm_client.py
    # without touching any agent or router code.
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 1024
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # --- Guardrail / usage ---
    daily_message_limit_default: int = 50

    # --- Web/official-source lookups (used by search_official_sources) ---
    tavily_api_key: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
