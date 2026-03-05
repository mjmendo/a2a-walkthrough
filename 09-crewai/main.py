"""
main.py — Runs the CrewAI A2A patterns research crew and prints results.

Run:
    python main.py

What you will see:
  1. researcher executes Task 1 — mock research report.
  2. analyst    executes Task 2 — mock comparison matrix (receives Task 1 context).
  3. writer     executes Task 3 — mock executive summary (receives Tasks 1+2 context).
  4. Final crew output is printed.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from crew import build_crew

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
CYAN  = "\033[96m"
GREEN = "\033[92m"
BOLD  = "\033[1m"
RESET = "\033[0m"


def main() -> None:
    """Kick off the crew and print the final combined output."""
    print(f"\n{BOLD}{CYAN}=== CrewAI A2A Patterns Research Demo ==={RESET}")
    print(
        f"{CYAN}Crew members:{RESET} "
        "Senior Researcher, Tech Analyst, Technical Writer"
    )
    print(f"{CYAN}Process:{RESET} Sequential\n")

    crew = build_crew()

    print(f"{CYAN}Kicking off crew ...{RESET}\n")
    result = crew.kickoff()

    print(f"\n{BOLD}{CYAN}=== Crew Execution Complete ==={RESET}")
    print(f"\n{GREEN}Final Output (writer's executive summary):{RESET}")

    # CrewAI >= 0.80 returns a CrewOutput object; .raw gives the string.
    raw = getattr(result, "raw", None) or str(result)
    print(raw)

    print(f"\n{BOLD}{CYAN}=== Done ==={RESET}\n")


if __name__ == "__main__":
    main()
