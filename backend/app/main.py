from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Base, engine
from app.mcp_bridge import start_persistent_session, stop_persistent_session
from app.routers import chat, plan, kb, usage, health, documents

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the MCP server subprocess + session ONCE for the app's
    # lifetime, not per chat turn -- spawning a fresh subprocess per
    # message caused real request failures under load on a
    # resource-constrained host (see app/mcp_bridge.py for detail).
    #
    # Run via asyncio.to_thread, not a direct call: start_persistent_session()
    # blocks internally (it spins up anyio's own background thread and
    # waits on it), and calling a blocking function directly on the same
    # event-loop thread that lifespan itself runs on deadlocks.
    await asyncio.to_thread(start_persistent_session)
    try:
        yield
    finally:
        await asyncio.to_thread(stop_persistent_session)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

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
