"""
Demo runner for Pattern 4: Blackboard.

Seeds the blackboard with a topic, then runs three specialist agents
sequentially. After each agent runs, the current blackboard state is
printed so you can see incremental contributions.

Requires Redis on localhost:6379 (start with: docker-compose up redis).
"""

import redis

from agents import OutlineAgent, ReviewerAgent, WriterAgent
from blackboard import Blackboard

CYAN = "\033[96m"
MAGENTA = "\033[95m"
GREEN = "\033[92m"
RESET = "\033[0m"

TOPIC = "distributed consensus algorithms in fault-tolerant systems"


def print_blackboard_state(bb: Blackboard, label: str) -> None:
    """Print all current blackboard keys and their status flags."""
    print(f"\n{MAGENTA}--- Blackboard state after: {label} ---{RESET}")
    content = bb.read_all()
    if not content:
        print("  (empty)")
        return
    for key, value in content.items():
        status = bb.get_status(key) or "—"
        preview = value[:80] + "..." if len(value) > 80 else value
        print(f"  {GREEN}{key!r}{RESET} [{status}]: {preview!r}")
    print()


def main() -> None:
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    bb = Blackboard(r)

    # Clear any leftover state from previous runs
    bb.clear()

    print(f"\n{CYAN}=== Blackboard Pattern Demo ==={RESET}")
    print(f"Topic: {TOPIC!r}\n")

    # Seed the blackboard with the initial topic
    bb.write("topic", TOPIC)
    bb.set_status("topic", "seeded")
    print_blackboard_state(bb, "seeding topic")

    # Step 1: OutlineAgent reads topic, writes outline
    OutlineAgent(bb).run()
    print_blackboard_state(bb, "OutlineAgent")

    # Step 2: WriterAgent reads outline, writes draft
    WriterAgent(bb).run()
    print_blackboard_state(bb, "WriterAgent")

    # Step 3: ReviewerAgent reads draft, writes review
    ReviewerAgent(bb).run()
    print_blackboard_state(bb, "ReviewerAgent")

    # Final: print the review
    review = bb.read("review")
    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{CYAN}  Final Review:{RESET}")
    print(f"{CYAN}{'='*60}{RESET}")
    print(review)
    print()


if __name__ == "__main__":
    main()
