"""
Synchronous bridge from app.agent (sync, deterministic) to app.mcp_client
(async MCP protocol client).

This is what makes the live agent's tool calls genuinely go THROUGH the
Model Context Protocol -- list_tools() + call_tool() over a real stdio
session with app.mcp_server -- rather than importing the underlying
functions directly. The intent routing in agent.py stays deterministic
(no LLM decides which tool to call); this module only changes HOW a
chosen tool gets invoked.

Uses anyio's blocking portal (not a bare asyncio event loop) because the
MCP client's async context managers use anyio cancel scopes internally,
which require entry and exit to happen within the same underlying task --
a plain `loop.run_until_complete()` per call violates that. The portal
runs one persistent background task for the whole turn, so the session
can be opened, used for several calls, and cleanly closed.

One MCP session is opened per chat turn (see mcp_turn()) and reused for
every tool call within that turn, rather than spawning a new server
subprocess per call.

Production note: for higher traffic, replace the per-turn portal/session
with one long-lived portal opened at app startup and reused across
requests.
"""
from contextlib import contextmanager

import anyio.from_thread

from app.mcp_client import mcp_session, call_tool


class _SyncMCPSession:
    """One open MCP session plus the background portal that runs it,
    exposing a plain synchronous .call() method."""

    def __init__(self, portal: anyio.from_thread.BlockingPortal, session):
        self._portal = portal
        self._session = session

    def call(self, tool_name: str, arguments: dict):
        return self._portal.call(call_tool, self._session, tool_name, arguments)


@contextmanager
def mcp_turn():
    """Context manager: opens one MCP session (one server subprocess),
    backed by one anyio blocking portal, for the duration of a `with`
    block -- yielding a sync-callable wrapper.

    Uses portal.wrap_async_context_manager(), anyio's purpose-built
    bridge for entering/exiting one async context manager safely from
    synchronous code across multiple calls -- a bare portal.call() on
    __aenter__/__aexit__ separately schedules them as different tasks
    and violates anyio's cancel-scope task affinity."""
    with anyio.from_thread.start_blocking_portal() as portal:
        with portal.wrap_async_context_manager(mcp_session()) as session:
            yield _SyncMCPSession(portal, session)


def encode_file(raw_bytes: bytes) -> str:
    """Helper for callers of upload_and_extract_document -- MCP tool
    arguments must be JSON-serializable, so file bytes travel as base64."""
    import base64

    return base64.b64encode(raw_bytes).decode("ascii")
