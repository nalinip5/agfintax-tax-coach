from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Base, engine
from app.routers import chat, plan, kb, usage, health, documents

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dev convenience: create tables if they don't exist. In production, use
# a real migration tool (Alembic) against the Postgres database instead.
Base.metadata.create_all(bind=engine)

app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(plan.router, prefix="/api")
app.include_router(kb.router, prefix="/api")
app.include_router(usage.router, prefix="/api")
app.include_router(documents.router, prefix="/api")

# Note: app/mcp_server.py, app/mcp_client.py, and app/mcp_bridge.py remain
# in the codebase as a genuine, independently-tested MCP server/client
# pair -- runnable standalone (`python -m app.mcp_server`) for an
# LLM-driven host or Claude Desktop -- but the live chat path above no
# longer depends on spawning that subprocess for every request. See
# app/agent.py for why.
