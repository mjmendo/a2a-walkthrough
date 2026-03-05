"""
main.py — Initiates the AutoGen group chat and prints the conversation transcript.

Run:
    python main.py

What you will see:
  1. user_proxy sends the initial task to the group.
  2. planner responds with a structured PLAN.
  3. executor executes Step 1, Step 2, Step 3 sequentially.
  4. planner reviews all outputs and sends TERMINATE.
  5. The full conversation transcript is printed.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import mock_responses  # reset state before run
mock_responses.reset_state()

from agents import build_agents, build_group_chat

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
CYAN  = "\033[96m"
GREEN = "\033[92m"
BOLD  = "\033[1m"
RESET = "\033[0m"


INITIAL_TASK = (
    "Research and document the 3 most important agent-to-agent (A2A) "
    "communication patterns.  For each pattern, include: mechanism, "
    "use cases, and trade-offs."
)


def print_transcript(messages: list[dict]) -> None:
    """Pretty-print the full conversation history."""
    colours = {
        "user_proxy": GREEN,
        "planner":    CYAN,
        "executor":   "\033[93m",  # yellow
    }
    print(f"\n{BOLD}{CYAN}=== Conversation Transcript ==={RESET}\n")
    for i, msg in enumerate(messages, start=1):
        sender = msg.get("name", msg.get("role", "unknown"))
        content = msg.get("content", "")
        colour = colours.get(sender, RESET)
        print(f"{colour}[{i}] {sender.upper()}{RESET}")
        print(content[:500] + ("..." if len(content) > 500 else ""))
        print()


def main() -> None:
    """Build agents, start group chat, print transcript."""
    print(f"\n{BOLD}{CYAN}=== AutoGen Group Chat Demo ==={RESET}")
    print(f"{CYAN}Agents:{RESET} user_proxy, planner, executor")
    print(f"{CYAN}Mode:{RESET} GroupChat with custom speaker selection\n")

    user_proxy, planner, executor = build_agents()
    groupchat, manager = build_group_chat(user_proxy, planner, executor)

    print(f"{CYAN}Initiating conversation ...{RESET}\n")

    # initiate_chat kicks off the group conversation.
    # user_proxy sends INITIAL_TASK; the GroupChatManager drives subsequent turns.
    user_proxy.initiate_chat(
        recipient=manager,
        message=INITIAL_TASK,
        clear_history=True,
    )

    # Print the full transcript from the shared groupchat history
    print_transcript(groupchat.messages)

    print(f"{BOLD}{CYAN}=== Done ==={RESET}\n")
    print(f"Total messages in conversation: {len(groupchat.messages)}")


if __name__ == "__main__":
    main()
