"""
Specialist worker agents for Pattern 2: Hierarchical Delegation.

Workers are leaf nodes in the hierarchy: they receive a single well-scoped
task, perform it, and return a result. They have no awareness of each other
or of the orchestrator's broader goal.
"""

import time


class ResearchWorker:
    """
    Simulates a research agent that investigates a topic.

    In a real system this might call a search API, query a database,
    or invoke an LLM. Here it returns a deterministic mock finding.
    """

    def __init__(self, worker_id: str = "research-1"):
        self.worker_id = worker_id

    def research(self, topic: str) -> str:
        """
        Return a fake research finding for the given topic.

        Args:
            topic: The subject to investigate.

        Returns:
            A string summarising the (mock) findings.
        """
        # Simulate work
        time.sleep(0.05)
        words = topic.lower().split()
        keyword = words[-1] if words else topic
        finding = (
            f"Finding on '{topic}': studies show that {keyword} "
            f"exhibits non-trivial behaviour under controlled conditions. "
            f"Sample size: {len(topic) * 7}. Confidence: high."
        )
        return finding


class SummaryWorker:
    """
    Simulates a summarisation agent that synthesises multiple research findings.

    Receives a list of finding strings and collapses them into a single
    executive-summary paragraph.
    """

    def __init__(self, worker_id: str = "summary-1"):
        self.worker_id = worker_id

    def summarise(self, findings: list[str]) -> str:
        """
        Combine multiple findings into a single summary.

        Args:
            findings: List of research-finding strings.

        Returns:
            A combined summary string.
        """
        time.sleep(0.05)
        count = len(findings)
        combined_keywords = ", ".join(
            f.split("'")[1] if "'" in f else f"topic-{i}"
            for i, f in enumerate(findings)
        )
        summary = (
            f"EXECUTIVE SUMMARY ({count} sources analysed): "
            f"Research covered [{combined_keywords}]. "
            f"All findings converge on consistent patterns. "
            f"Recommendation: proceed with confidence. "
            f"Total evidence units: {sum(len(f) for f in findings)}."
        )
        return summary
