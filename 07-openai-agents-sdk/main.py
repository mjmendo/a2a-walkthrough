"""
main.py — Demonstrates the OpenAI Agents SDK handoff pattern end-to-end.

Run:
    python main.py

What you will see:
  1. A billing question → triage routes to billing_agent → billing_agent answers.
  2. A technical question → triage routes to tech_agent → tech_agent answers.
  3. An ambiguous question → triage cannot decide, asks for clarification.

The handoff events are printed as they happen, mimicking the trace output you
would see in the real OpenAI Agents SDK dashboard.
"""

from __future__ import annotations

import sys
import os

# Allow running from the repo root or from inside the directory
sys.path.insert(0, os.path.dirname(__file__))

from agents_setup import Agent, build_agents

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


# ---------------------------------------------------------------------------
# Runner — the core loop (mirrors SDK's Runner.run())
# ---------------------------------------------------------------------------

HANDOFF_PREFIX = "HANDOFF:"


def run(starting_agent: Agent, user_message: str, max_turns: int = 5) -> str:
    """
    Execute the agent loop for a single user message.

    Algorithm (matches the real SDK's internal loop):
      1. Call current_agent.response_fn(user_message)  ← mock replaces model call
      2. If response starts with "HANDOFF:<name>":
           a. Find the target agent in current_agent.handoffs
           b. Print a handoff event (the SDK emits HandoffEvent)
           c. Switch current_agent to the target
           d. Call target agent with the original user_message
      3. Return the final plain-text response.

    Returns:
        The final agent's response text.
    """
    current_agent = starting_agent
    response = ""

    for turn in range(max_turns):
        print(f"  {YELLOW}[turn {turn + 1}]{RESET} agent={current_agent.name!r}")

        if current_agent.response_fn is None:
            raise RuntimeError(f"Agent {current_agent.name!r} has no response_fn set.")

        response = current_agent.response_fn(user_message)

        if response.startswith(HANDOFF_PREFIX):
            target_name = response[len(HANDOFF_PREFIX):]
            # Locate the target in this agent's declared handoffs
            target = next(
                (a for a in current_agent.handoffs if a.name == target_name),
                None,
            )
            if target is None:
                print(f"  {MAGENTA}[handoff FAILED]{RESET} unknown target={target_name!r}")
                break

            print(
                f"  {MAGENTA}[HandoffEvent]{RESET} "
                f"{current_agent.name!r} → {target.name!r}"
            )
            current_agent = target
            # The new agent receives the original user message (SDK behaviour:
            # the full conversation history is carried over, but for this demo
            # we keep it simple with a single user turn).
        else:
            # Plain response — conversation ends here
            break

    return response


# ---------------------------------------------------------------------------
# Demo conversations
# ---------------------------------------------------------------------------

DEMO_CASES: list[tuple[str, str]] = [
    (
        "billing",
        "I was charged twice for my subscription last month and I need a refund.",
    ),
    (
        "technical",
        "I keep getting a 401 error when calling the API — how do I debug this?",
    ),
    (
        "ambiguous",
        "Can you help me with something?",
    ),
]


def main() -> None:
    """Run all demo conversations and print handoff traces."""
    agents = build_agents()
    triage = agents["triage_agent"]

    print(f"\n{BOLD}{CYAN}=== OpenAI Agents SDK — Handoff Pattern Demo ==={RESET}")
    print(
        f"{CYAN}Agents defined:{RESET} "
        + ", ".join(a.name for a in agents.values())
    )
    print(f"{CYAN}Entry point:{RESET} triage_agent\n")

    for label, message in DEMO_CASES:
        print(f"{BOLD}{'─' * 60}{RESET}")
        print(f"{BOLD}Scenario: {label.upper()}{RESET}")
        print(f"{GREEN}User:{RESET} {message}")
        print(f"{CYAN}Trace:{RESET}")

        final_response = run(triage, message)

        print(f"{GREEN}Final response:{RESET} {final_response}")
        print()

    print(f"{BOLD}{CYAN}=== Done ==={RESET}\n")


if __name__ == "__main__":
    main()
