"""
A2A client — discovers and interacts with the Echo Agent.

Demonstrates the full A2A interaction lifecycle:
  Step 1: Discovery   — fetch Agent Card from /.well-known/agent.json
  Step 2: Task send   — call tasks/send via JSON-RPC 2.0
  Step 3: SSE stream  — subscribe to the streaming endpoint and print events
  Step 4: Summary     — show the full conversation (input → output)

Run this script while the server is up:
    uvicorn agent_server:app --port 8005
    python agent_client.py
"""

from __future__ import annotations

import json
import uuid

import httpx

BASE_URL = "http://localhost:8005"

# ANSI colours
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


# ---------------------------------------------------------------------------
# Step 1 — Discovery
# ---------------------------------------------------------------------------


def fetch_agent_card(client: httpx.Client) -> dict:
    """
    Fetch the Agent Card from the well-known URL.

    This is always the first step in A2A: discover what the agent can do
    before committing to a task contract.
    """
    print(f"\n{BOLD}{CYAN}=== Step 1: Agent Discovery ==={RESET}")
    url = f"{BASE_URL}/.well-known/agent.json"
    print(f"  GET {url}")
    resp = client.get(url)
    resp.raise_for_status()
    card = resp.json()
    print(f"  {GREEN}Agent name   :{RESET} {card['name']}")
    print(f"  {GREEN}Version      :{RESET} {card['version']}")
    print(f"  {GREEN}Description  :{RESET} {card['description']}")
    print(f"  {GREEN}Streaming    :{RESET} {card['capabilities']['streaming']}")
    print(f"  {GREEN}Skills       :{RESET}")
    for skill in card.get("skills", []):
        print(f"    - [{skill['id']}] {skill['name']}: {skill['description']}")
    return card


# ---------------------------------------------------------------------------
# Step 2 — tasks/send
# ---------------------------------------------------------------------------


def send_task(client: httpx.Client, text: str) -> dict:
    """
    Send a task using JSON-RPC 2.0.

    JSON-RPC 2.0 wraps the method call in a standardised envelope so
    that multiple methods can share a single HTTP endpoint (/rpc) and
    responses can be correlated by ``id``.
    """
    print(f"\n{BOLD}{YELLOW}=== Step 2: Send Task (JSON-RPC tasks/send) ==={RESET}")
    task_id = str(uuid.uuid4())
    rpc_request = {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "tasks/send",
        "params": {
            "taskId": task_id,
            "message": {
                "role": "user",
                "parts": [{"type": "text", "content": text}],
            },
        },
    }
    print(f"  POST {BASE_URL}/rpc")
    print(f"  {YELLOW}Input text   :{RESET} {text!r}")
    print(f"  {YELLOW}Task ID      :{RESET} {task_id}")

    resp = client.post(f"{BASE_URL}/rpc", json=rpc_request)
    resp.raise_for_status()
    body = resp.json()

    if "error" in body:
        print(f"  {MAGENTA}JSON-RPC error: {body['error']}{RESET}")
        return {}

    result = body.get("result", {})
    output_parts = result.get("output", {}).get("parts", [])
    output_text = " ".join(p["content"] for p in output_parts if p.get("type") == "text")
    print(f"  {GREEN}Status       :{RESET} {result.get('status')}")
    print(f"  {GREEN}Output text  :{RESET} {output_text!r}")
    return result


# ---------------------------------------------------------------------------
# Step 3 — SSE stream
# ---------------------------------------------------------------------------


def stream_task_events(client: httpx.Client, task_id: str) -> None:
    """
    Subscribe to the SSE stream for a task and print each event.

    SSE (Server-Sent Events) allows the server to push incremental
    updates over a single long-lived HTTP connection — no polling needed.
    Each event has an ``event`` type and a JSON ``data`` payload.
    """
    print(f"\n{BOLD}{MAGENTA}=== Step 3: SSE Stream ==={RESET}")
    url = f"{BASE_URL}/rpc/stream/{task_id}"
    print(f"  GET {url}  (streaming)")

    # httpx streams the response line-by-line
    with client.stream("GET", url, timeout=10.0) as resp:
        resp.raise_for_status()
        for raw_line in resp.iter_lines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                data_str = line[len("data:"):].strip()
                try:
                    event_data = json.loads(data_str)
                    status = event_data.get("status", "?")
                    step = event_data.get("step", "")
                    step_label = f"  step={step}" if step else ""
                    print(f"  {MAGENTA}[SSE event]{RESET} status={status!r}{step_label}")
                except json.JSONDecodeError:
                    print(f"  [SSE raw] {data_str}")


# ---------------------------------------------------------------------------
# Step 4 — conversation summary
# ---------------------------------------------------------------------------


def show_conversation(user_text: str, result: dict) -> None:
    """Print a clean turn-by-turn view of the task exchange."""
    print(f"\n{BOLD}{BLUE}=== Step 4: Full Conversation ==={RESET}")
    print(f"  {YELLOW}user  >{RESET} {user_text!r}")
    output = result.get("output") or {}
    parts = output.get("parts", [])
    agent_text = " ".join(p["content"] for p in parts if p.get("type") == "text")
    print(f"  {GREEN}agent >{RESET} {agent_text!r}")
    print(f"  {BLUE}status: {result.get('status')}{RESET}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the full A2A interaction demo."""
    print(f"\n{BOLD}{CYAN}{'='*55}{RESET}")
    print(f"{BOLD}{CYAN}  A2A Client Demo — Echo Agent Walkthrough{RESET}")
    print(f"{BOLD}{CYAN}{'='*55}{RESET}")

    sample_text = "hello from the A2A client"

    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        # 1. Discover
        fetch_agent_card(client)

        # 2. Send task and get synchronous result
        result = send_task(client, sample_text)

        # 3. Watch the SSE stream for this task
        task_id = result.get("id", str(uuid.uuid4()))
        stream_task_events(client, task_id)

        # 4. Show full conversation
        if result:
            show_conversation(sample_text, result)

    print(f"\n{CYAN}=== Done ==={RESET}\n")


if __name__ == "__main__":
    main()
