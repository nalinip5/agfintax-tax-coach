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
a plain `loop.run_until_complete()` per call violates that.

IMPORTANT: this maintains ONE PERSISTENT session for the whole app
lifetime (started at FastAPI startup, closed at shutdown) -- NOT one
session per chat turn. Spawning a fresh Python subprocess (interpreter
startup + importing the whole app + protocol handshake) on every single
message is real overhead that caused actual request failures/timeouts
under real traffic on a resource-constrained host, even though it worked
fine for a single manual curl test. One long-lived session avoids that
entirely; WEB_CONCURRENCY=1 means a single worker process handles all
requests anyway, so one shared session is both safe and correct here.
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


_state: dict = {"portal": None, "portal_cm": None, "wrapped": None, "session": None}


def start_persistent_session() -> None:
    """Call once, at app startup. Spawns the MCP server subprocess ONCE
    and keeps the session open for the app's lifetime."""
    if _state["session"] is not None:
        return  # already started
    portal_cm = anyio.from_thread.start_blocking_portal()
    portal = portal_cm.__enter__()
    wrapped = portal.wrap_async_context_manager(mcp_session())
    session = wrapped.__enter__()
    _state.update(portal=portal, portal_cm=portal_cm, wrapped=wrapped, session=session)


def stop_persistent_session() -> None:
    """Call once, at app shutdown. Must exit the SAME wrapped context
    manager instance that start_persistent_session() entered -- creating
    a fresh wrap_async_context_manager() call here for __exit__ hangs
    indefinitely, since anyio's cancel-scope bookkeeping is tied to that
    specific instance, not just the underlying session object."""
    if _state["session"] is None:
        return
    wrapped = _state["wrapped"]
    portal_cm = _state["portal_cm"]
    try:
        wrapped.__exit__(None, None, None)
    finally:
        portal_cm.__exit__(None, None, None)
    _state.update(portal=None, portal_cm=None, wrapped=None, session=None)


def get_mcp() -> _SyncMCPSession:
    """Returns the persistent session for use in a request. Falls back to
    lazily starting one if the app didn't call start_persistent_session()
    (e.g. in tests) so callers never crash on a missing session."""
    if _state["session"] is None:
        start_persistent_session()
    return _SyncMCPSession(_state["portal"], _state["session"])


@contextmanager
def mcp_turn():
    """Back-compat context-manager form -- now just yields the shared
    persistent session rather than opening a new one, so existing
    `with mcp_turn() as mcp:` call sites keep working unchanged."""
    yield get_mcp()


def encode_file(raw_bytes: bytes) -> str:
    """Helper for callers of upload_and_extract_document -- MCP tool
    arguments must be JSON-serializable, so file bytes travel as base64."""
    import base64

    return base64.b64encode(raw_bytes).decode("ascii")
