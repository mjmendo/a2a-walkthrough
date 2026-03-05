"""
Agent A — HTTP client that sends tasks to Agent B and prints responses.

This script demonstrates the request/response cycle: Agent A is the
*caller* and Agent B is the *callee*. The coupling is direct and tight:
Agent A must know Agent B's URL and schema.
"""

import httpx

AGENT_B_URL = "http://localhost:8001/task"

SAMPLE_INPUTS = [
    "hello world",
    "agent to agent communication",
    "Python 3.11 is great",
]

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def send_task(client: httpx.Client, text: str) -> dict:
    """Send a single task to Agent B and return the parsed JSON response."""
    response = client.post(AGENT_B_URL, json={"input": text})
    response.raise_for_status()
    return response.json()


def main() -> None:
    """Send 3 tasks to Agent B, print each request/response pair."""
    print(f"\n{CYAN}=== Agent A: Direct Request-Response Demo ==={RESET}\n")

    with httpx.Client(timeout=10.0) as client:
        for i, text in enumerate(SAMPLE_INPUTS, start=1):
            print(f"{YELLOW}[Request {i}]{RESET} input={text!r}")
            result = send_task(client, text)
            print(f"{GREEN}[Response {i}]{RESET} result={result['result']!r}  agent={result['agent']!r}\n")

    print(f"{CYAN}=== Done ==={RESET}\n")


if __name__ == "__main__":
    main()
