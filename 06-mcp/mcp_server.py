"""
MCP server exposing three tools via the official Python MCP SDK.

Uses ``FastMCP`` — the high-level decorator-based API from the ``mcp`` package.
The default transport is **stdio**, which means the server communicates over
stdin/stdout when launched as a subprocess by an MCP host or client.

Tools exposed:
  1. get_weather(city)               — mock weather data
  2. search_knowledge_base(query)    — mock KB search returning 3 snippets
  3. create_summary(texts, max_words) — mock summarisation

Why stdio?  It's the simplest transport: no port binding, no TLS setup, and
it works inside any process sandbox.  The MCP SDK also supports SSE and
Streamable HTTP for network-accessible servers.

References:
  https://modelcontextprotocol.io/introduction
  https://github.com/modelcontextprotocol/python-sdk
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

# Create the FastMCP application.  The string is the server's display name.
mcp = FastMCP("Demo MCP Server")


# ---------------------------------------------------------------------------
# Tool 1 — get_weather
# ---------------------------------------------------------------------------


@mcp.tool()
def get_weather(city: str) -> str:
    """
    Return mock current weather for a given city.

    In a real implementation this would call an external weather API
    (e.g. OpenWeatherMap).  We return a deterministic string so the demo
    needs zero network access.

    Args:
        city: The city name to look up.

    Returns:
        A human-readable weather description string.
    """
    # Fake weather database keyed by lower-cased city name
    weather_db: dict[str, str] = {
        "london": "Overcast, 14°C, humidity 82%, light drizzle",
        "new york": "Partly cloudy, 22°C, humidity 55%, gentle breeze",
        "tokyo": "Sunny, 28°C, humidity 68%, calm winds",
        "sydney": "Clear sky, 19°C, humidity 61%, SE wind 15 km/h",
        "paris": "Cloudy, 17°C, humidity 74%, chance of showers",
    }

    key = city.strip().lower()
    if key in weather_db:
        return f"Weather in {city}: {weather_db[key]}"
    return f"Weather in {city}: Partly cloudy, 20°C, humidity 60% (mock fallback)"


# ---------------------------------------------------------------------------
# Tool 2 — search_knowledge_base
# ---------------------------------------------------------------------------


@mcp.tool()
def search_knowledge_base(query: str) -> list[str]:
    """
    Search a mock knowledge base and return up to 3 relevant snippets.

    A real implementation would query a vector database (Pinecone, pgvector,
    Weaviate, etc.).  We return hardcoded snippets relevant to common AI/agent
    queries so the demo is self-contained.

    Args:
        query: The search query string.

    Returns:
        A list of up to 3 text snippets that match the query.
    """
    # Mock corpus — keyword → snippets
    corpus: dict[str, list[str]] = {
        "mcp": [
            "MCP (Model Context Protocol) is an open standard by Anthropic for LLM↔tool interoperability.",
            "MCP defines three primitives: tools (functions), resources (data), and prompts (templates).",
            "MCP supports three transports: stdio, SSE, and Streamable HTTP.",
        ],
        "a2a": [
            "Google A2A (Agent-to-Agent) protocol enables cross-vendor agent interoperability.",
            "A2A uses JSON-RPC 2.0 over HTTP and SSE for streaming task updates.",
            "Agent discovery in A2A relies on the well-known Agent Card at /.well-known/agent.json.",
        ],
        "agent": [
            "An AI agent is a system that perceives its environment and takes actions to achieve goals.",
            "Agentic workflows often combine LLM reasoning with tool use and memory.",
            "Multi-agent systems let specialised agents collaborate on complex tasks.",
        ],
        "llm": [
            "Large Language Models (LLMs) are trained on massive text corpora using self-supervised learning.",
            "LLMs can be prompted with tool descriptions so they can plan tool invocations.",
            "Fine-tuning and RLHF are common techniques to align LLM behaviour.",
        ],
    }

    query_lower = query.lower()
    # Find the first corpus key that appears in the query
    for key, snippets in corpus.items():
        if key in query_lower:
            return snippets[:3]

    # Generic fallback
    return [
        f"No specific results for '{query}' in the mock knowledge base.",
        "Try searching for: mcp, a2a, agent, or llm.",
        "In production, this would perform a vector similarity search.",
    ]


# ---------------------------------------------------------------------------
# Tool 3 — create_summary
# ---------------------------------------------------------------------------


@mcp.tool()
def create_summary(texts: list[str], max_words: int = 50) -> str:
    """
    Generate a mock summary of the provided texts within a word budget.

    A real implementation would call an LLM or a summarisation model.
    We concatenate, truncate to ``max_words``, and append an ellipsis
    so the demo is deterministic and fast.

    Args:
        texts:     List of text strings to summarise.
        max_words: Maximum number of words in the output summary.

    Returns:
        A summary string (truncated if necessary).
    """
    if not texts:
        return "No texts provided to summarise."

    combined = " ".join(t.strip() for t in texts if t.strip())
    words = combined.split()

    if len(words) <= max_words:
        summary = combined
    else:
        summary = " ".join(words[:max_words]) + "…"

    return f"[Summary ({min(len(words), max_words)} words)]: {summary}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # mcp.run() defaults to the stdio transport.
    # The MCP host (or mcp_client.py) launches this script as a subprocess
    # and communicates over its stdin/stdout pipes.
    mcp.run()
