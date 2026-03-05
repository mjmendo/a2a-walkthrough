"""
Integration tests for Pattern 6: Anthropic MCP.

Tests use the ``mcp`` Python SDK to connect to the server in-process via
in-memory streams — no subprocess or network needed.

The ``FastMCP`` instance exposes a ``run_stdio_async()`` coroutine, but for
testing it is simpler to use the lower-level ``create_connected_server_and_client_session``
helper from ``mcp.shared.memory``, which wires a server and client together
over in-memory streams.

If that helper is unavailable in the installed SDK version we fall back to
launching the server as a subprocess via stdio_client (same as mcp_client.py).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import anyio
import pytest

# We import the FastMCP instance directly so we can wire it in-process.
from mcp_server import mcp

SERVER_SCRIPT = str(Path(__file__).parent / "mcp_server.py")


# ---------------------------------------------------------------------------
# Helpers — in-process session fixture
# ---------------------------------------------------------------------------


async def _get_session():
    """
    Create an in-process MCP client session connected to our FastMCP server.

    We use ``mcp.shared.memory.create_connected_server_and_client_session``
    when available; otherwise we fall back to a subprocess-based connection.
    """
    try:
        from mcp.shared.memory import create_connected_server_and_client_session

        return await create_connected_server_and_client_session(mcp._mcp_server)
    except (ImportError, AttributeError):
        # Older SDK versions: connect via subprocess stdio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])
        # We return a context manager — callers must handle this case
        return None


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def session():
    """
    Pytest fixture that yields a connected MCP ClientSession.

    Uses anyio to run the async setup/teardown around each test.
    """
    # We implement each test as a sync wrapper around an async coroutine,
    # which is the most portable approach across anyio backends.
    pass


# ---------------------------------------------------------------------------
# Utility: run a single async test function
# ---------------------------------------------------------------------------


def _run(coro):
    """Run a coroutine in a new event loop (used by each test)."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tests — via subprocess stdio (universally compatible)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def event_loop():
    """Reuse a single event loop across module-scoped async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def _with_session(coro_fn):
    """
    Connect to the MCP server (subprocess) and execute coro_fn(session).

    This works regardless of SDK internals because it uses the same
    public stdio_client API that mcp_client.py uses.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            return await coro_fn(session)


# ---------------------------------------------------------------------------
# Test: list_tools
# ---------------------------------------------------------------------------


class TestListTools:
    def test_tool_count(self):
        async def _check(session):
            result = await session.list_tools()
            return result.tools

        tools = asyncio.run(_with_session(_check))
        assert len(tools) == 3, f"Expected 3 tools, got {len(tools)}"

    def test_tool_names(self):
        async def _check(session):
            result = await session.list_tools()
            return [t.name for t in result.tools]

        names = asyncio.run(_with_session(_check))
        assert "get_weather" in names
        assert "search_knowledge_base" in names
        assert "create_summary" in names

    def test_tools_have_descriptions(self):
        async def _check(session):
            result = await session.list_tools()
            return [(t.name, t.description) for t in result.tools]

        pairs = asyncio.run(_with_session(_check))
        for name, desc in pairs:
            assert desc, f"Tool {name!r} has an empty description"

    def test_tools_have_input_schema(self):
        async def _check(session):
            result = await session.list_tools()
            return [(t.name, t.inputSchema) for t in result.tools]

        pairs = asyncio.run(_with_session(_check))
        for name, schema in pairs:
            assert schema is not None, f"Tool {name!r} is missing inputSchema"


# ---------------------------------------------------------------------------
# Test: get_weather
# ---------------------------------------------------------------------------


class TestGetWeather:
    def _call(self, city: str) -> str:
        async def _check(session):
            result = await session.call_tool("get_weather", {"city": city})
            return result.content[0].text

        return asyncio.run(_with_session(_check))

    def test_known_city(self):
        result = self._call("London")
        assert "London" in result
        assert "°C" in result

    def test_unknown_city_returns_fallback(self):
        result = self._call("Atlantis")
        assert "Atlantis" in result
        assert "mock fallback" in result

    def test_returns_string(self):
        result = self._call("Tokyo")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Test: search_knowledge_base
# ---------------------------------------------------------------------------


class TestSearchKnowledgeBase:
    def _call(self, query: str) -> str:
        async def _check(session):
            result = await session.call_tool("search_knowledge_base", {"query": query})
            return result.content[0].text

        return asyncio.run(_with_session(_check))

    def test_mcp_query_returns_relevant_snippet(self):
        result = self._call("what is mcp")
        # The result is serialised as a string (JSON list or plain text)
        assert "MCP" in result or "Model Context Protocol" in result

    def test_a2a_query(self):
        result = self._call("a2a protocol")
        assert "A2A" in result or "Agent" in result

    def test_unknown_query_returns_fallback(self):
        result = self._call("quantum entanglement")
        assert "No specific results" in result or "mock knowledge base" in result


# ---------------------------------------------------------------------------
# Test: create_summary
# ---------------------------------------------------------------------------


class TestCreateSummary:
    def _call(self, texts: list[str], max_words: int = 50) -> str:
        async def _check(session):
            result = await session.call_tool(
                "create_summary",
                {"texts": texts, "max_words": max_words},
            )
            return result.content[0].text

        return asyncio.run(_with_session(_check))

    def test_basic_summary(self):
        result = self._call(["Hello world.", "This is a test."])
        assert "Summary" in result

    def test_empty_list(self):
        result = self._call([])
        assert "No texts" in result

    def test_truncation(self):
        long_texts = ["word " * 100]
        result = self._call(long_texts, max_words=5)
        # Should truncate — count words excluding the label prefix
        assert "…" in result

    def test_within_budget_no_ellipsis(self):
        result = self._call(["Hello world"], max_words=100)
        assert "…" not in result

    def test_returns_string(self):
        result = self._call(["test"])
        assert isinstance(result, str)
