"""
MCP client — demonstrates how an LLM host discovers and invokes MCP tools.

Lifecycle:
  1. Launch the MCP server as a subprocess (stdio transport)
  2. Initialise the MCP session
  3. List available tools — this is how an LLM host discovers capabilities
  4. Call each tool with sample inputs and pretty-print the results

This script intentionally shows the *raw* MCP interaction (no LLM involved)
so you can see exactly what the protocol exchanges before an LLM is added.

Run:
    python mcp_client.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ANSI colours
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Absolute path to the server script so the client works from any directory
SERVER_SCRIPT = str(Path(__file__).parent / "mcp_server.py")


# ---------------------------------------------------------------------------
# Step 1+2 — Launch server subprocess and initialise session
# ---------------------------------------------------------------------------


async def run_demo() -> None:
    """
    Full MCP client demo:
      - connect to the server via stdio
      - list tools
      - call each tool with sample inputs
    """
    print(f"\n{BOLD}{CYAN}{'='*55}{RESET}")
    print(f"{BOLD}{CYAN}  MCP Client Demo — Tool Discovery & Invocation{RESET}")
    print(f"{BOLD}{CYAN}{'='*55}{RESET}")

    # StdioServerParameters tells the MCP SDK how to launch the server.
    # The SDK forks a child process and wires stdin/stdout as the transport.
    server_params = StdioServerParameters(
        command=sys.executable,   # same Python interpreter as the client
        args=[SERVER_SCRIPT],
        env=None,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialise performs the MCP handshake (capability negotiation)
            await session.initialize()
            print(f"\n{GREEN}[mcp_client] Session initialised{RESET}")

            # Step 3 — list tools
            await list_tools(session)

            # Step 4 — call each tool
            await call_get_weather(session)
            await call_search_knowledge_base(session)
            await call_create_summary(session)

    print(f"\n{CYAN}=== Done ==={RESET}\n")


# ---------------------------------------------------------------------------
# Step 3 — Tool discovery
# ---------------------------------------------------------------------------


async def list_tools(session: ClientSession) -> None:
    """
    Ask the server for its tool list.

    An LLM host sends this exact call at startup so the model can know which
    tools are available and what their input schemas look like.
    """
    print(f"\n{BOLD}{YELLOW}=== Step 3: List Available Tools ==={RESET}")
    tools_result = await session.list_tools()

    for tool in tools_result.tools:
        print(f"\n  {GREEN}Tool:{RESET} {tool.name}")
        print(f"  {GREEN}Desc:{RESET} {tool.description}")
        # The inputSchema is a JSON Schema object the LLM uses to format calls
        schema = tool.inputSchema
        if schema and schema.get("properties"):
            for param_name, param_info in schema["properties"].items():
                ptype = param_info.get("type", "any")
                pdesc = param_info.get("description", "")
                print(f"    {MAGENTA}param{RESET} {param_name!r} ({ptype}): {pdesc}")


# ---------------------------------------------------------------------------
# Step 4 — Tool invocations
# ---------------------------------------------------------------------------


async def call_get_weather(session: ClientSession) -> None:
    """Call the get_weather tool and print results."""
    print(f"\n{BOLD}{BLUE}=== Step 4a: call_tool('get_weather') ==={RESET}")
    cities = ["London", "Tokyo", "Mars"]

    for city in cities:
        print(f"  {YELLOW}Input city:{RESET} {city!r}")
        result = await session.call_tool("get_weather", {"city": city})
        # result.content is a list of ContentBlock objects
        for block in result.content:
            print(f"  {GREEN}Result:{RESET} {block.text}")


async def call_search_knowledge_base(session: ClientSession) -> None:
    """Call the search_knowledge_base tool and print results."""
    print(f"\n{BOLD}{BLUE}=== Step 4b: call_tool('search_knowledge_base') ==={RESET}")
    queries = ["what is MCP?", "how does A2A work?"]

    for query in queries:
        print(f"  {YELLOW}Query:{RESET} {query!r}")
        result = await session.call_tool("search_knowledge_base", {"query": query})
        for block in result.content:
            # The tool returns a list; the SDK serialises it to a JSON string block
            print(f"  {GREEN}Snippets:{RESET}")
            # Parse the JSON list if needed, or print raw
            text = block.text if hasattr(block, "text") else str(block)
            print(f"    {text}")


async def call_create_summary(session: ClientSession) -> None:
    """Call the create_summary tool and print result."""
    print(f"\n{BOLD}{BLUE}=== Step 4c: call_tool('create_summary') ==={RESET}")
    texts = [
        "MCP is a standard for LLM tool interoperability.",
        "It defines tools, resources, and prompts as primitives.",
        "The stdio transport requires no network setup.",
        "An LLM host can discover tools at runtime via list_tools.",
    ]
    max_words = 20
    print(f"  {YELLOW}Input texts:{RESET} {len(texts)} items")
    print(f"  {YELLOW}Max words  :{RESET} {max_words}")
    result = await session.call_tool(
        "create_summary",
        {"texts": texts, "max_words": max_words},
    )
    for block in result.content:
        print(f"  {GREEN}Summary:{RESET} {block.text}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(run_demo())
