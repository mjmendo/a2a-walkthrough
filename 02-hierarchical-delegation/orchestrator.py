"""
Orchestrator for Pattern 2: Hierarchical Delegation.

The orchestrator owns the high-level goal and is responsible for:
  1. Decomposing it into subtasks.
  2. Delegating each subtask to the right specialist worker.
  3. Collecting results and producing a final answer.

Workers know nothing about each other or the overall goal — only their
specific subtask. All coordination logic lives here.
"""

from workers import ResearchWorker, SummaryWorker

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


class Orchestrator:
    """
    Decomposes a high-level goal into subtasks and delegates to specialists.

    Decomposition strategy (hard-coded for clarity):
      - Step 1: Research topic A  -> ResearchWorker
      - Step 2: Research topic B  -> ResearchWorker
      - Step 3: Summarise results -> SummaryWorker
    """

    def __init__(self):
        self.research_worker = ResearchWorker()
        self.summary_worker = SummaryWorker()

    def _decompose(self, goal: str) -> list[dict]:
        """
        Break a high-level goal into an ordered list of subtask descriptors.

        Each descriptor is a dict with keys: step, type, payload.
        """
        # Simple deterministic decomposition: treat the goal as two-part topic
        parts = goal.split(" and ", maxsplit=1)
        topic_a = parts[0].strip() if len(parts) > 0 else goal
        topic_b = parts[1].strip() if len(parts) > 1 else f"{goal} (secondary angle)"

        return [
            {"step": 1, "type": "research", "payload": topic_a},
            {"step": 2, "type": "research", "payload": topic_b},
            {"step": 3, "type": "summarise", "payload": None},  # filled at runtime
        ]

    def run(self, goal: str) -> dict:
        """
        Execute the full delegation pipeline for the given goal.

        Args:
            goal: High-level objective string.

        Returns:
            Dict with keys: goal, findings (list), summary (str).
        """
        print(f"\n{CYAN}{'='*60}{RESET}")
        print(f"{CYAN}  Orchestrator received goal:{RESET} {goal!r}")
        print(f"{CYAN}{'='*60}{RESET}\n")

        subtasks = self._decompose(goal)
        findings: list[str] = []

        for task in subtasks:
            step = task["step"]

            if task["type"] == "research":
                topic = task["payload"]
                print(f"{YELLOW}[Step {step}] Delegating to ResearchWorker{RESET} -> topic={topic!r}")
                finding = self.research_worker.research(topic)
                findings.append(finding)
                print(f"{GREEN}[Step {step}] ResearchWorker returned:{RESET} {finding}\n")

            elif task["type"] == "summarise":
                print(f"{YELLOW}[Step {step}] Delegating to SummaryWorker{RESET} -> {len(findings)} findings")
                summary = self.summary_worker.summarise(findings)
                print(f"{GREEN}[Step {step}] SummaryWorker returned:{RESET} {summary}\n")

        print(f"{MAGENTA}{'='*60}{RESET}")
        print(f"{MAGENTA}  Final answer assembled by Orchestrator{RESET}")
        print(f"{MAGENTA}{'='*60}{RESET}\n")

        return {"goal": goal, "findings": findings, "summary": summary}


if __name__ == "__main__":
    orchestrator = Orchestrator()
    result = orchestrator.run(
        "distributed systems fault tolerance and consensus algorithms"
    )
    print("RESULT KEYS:", list(result.keys()))
    print("SUMMARY:", result["summary"])
