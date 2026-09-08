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
    # Defaults to a local SQLite file so the app runs out of the box.
    # Point this at Supabase Postgres (or any standard Postgres) in
    # staging/production, e.g.:
    # postgresql+psycopg2://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
    database_url: str = "sqlite:///./agfintax.db"

    # --- Redis (optional cache / rate limiting) ---
    redis_url: Optional[str] = None

    # --- LLM provider (model-agnostic, ENV-driven) ---
    # Supported today: "anthropic", "openai". Add new providers in
    # llm_client.py / app/agent.py without touching router code.
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 1024
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # --- Guardrail / usage ---
    daily_message_limit_default: int = 50

    # --- Official-source live search (agent's search_official_sources tool) ---
    tavily_api_key: Optional[str] = None

    # --- Azure AI Document Intelligence (OCR for user document uploads) ---
    azure_di_endpoint: Optional[str] = None
    azure_di_key: Optional[str] = None

    # --- Clerk authentication ---
    # Backend verifies the JWT Clerk issues to the frontend; see app/auth.py.
    clerk_jwks_url: Optional[str] = None
    clerk_issuer: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
