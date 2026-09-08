"""
MCP client: connects to app.mcp_server as a subprocess over stdio,
discovers its tools dynamically via list_tools(), and calls them via
call_tool() -- the real protocol round-trip, not a hardcoded schema. This
is what the single agent (app/agent.py) uses when an LLM is configured to
drive tool selection.
"""
import json
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SERVER_PARAMS = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"])


@asynccontextmanager
async def mcp_session():
    """One MCP session per agent turn -- discover tools once, call
    several, then tear down the subprocess. (Production note: for higher
    traffic, keep one long-lived session across requests instead of
    spawning a subprocess per turn.)"""
    async with stdio_client(_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def list_tool_schemas(session: ClientSession) -> list[dict]:
    result = await session.list_tools()
    return [{"name": t.name, "description": t.description, "input_schema": t.inputSchema} for t in result.tools]


async def call_tool(session: ClientSession, name: str, arguments: dict):
    """The server always returns exactly one JSON-encoded string per tool
    (see mcp_server.py) -- no block-count ambiguity to resolve here."""
    result = await session.call_tool(name, arguments)
    for block in result.content:
        if block.type == "text":
            try:
                return json.loads(block.text)
            except (json.JSONDecodeError, TypeError):
                return block.text
    return None
