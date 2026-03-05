"""
Integration tests for Pattern 2: Hierarchical Delegation.

All tests run in-process with no network or external dependencies.
"""

import pytest

from orchestrator import Orchestrator
from workers import ResearchWorker, SummaryWorker


# ---------------------------------------------------------------------------
# Unit tests for individual workers
# ---------------------------------------------------------------------------

class TestResearchWorker:
    def test_returns_string(self):
        worker = ResearchWorker()
        result = worker.research("machine learning")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_topic_appears_in_finding(self):
        worker = ResearchWorker()
        result = worker.research("quantum computing")
        # The last word of the topic should appear in the finding
        assert "computing" in result.lower()

    def test_empty_topic_does_not_crash(self):
        worker = ResearchWorker()
        result = worker.research("")
        assert isinstance(result, str)


class TestSummaryWorker:
    def test_returns_string(self):
        worker = SummaryWorker()
        result = worker.summarise(["finding 1", "finding 2"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_source_count_in_summary(self):
        worker = SummaryWorker()
        findings = ["a", "b", "c"]
        result = worker.summarise(findings)
        assert "3" in result  # count of sources

    def test_single_finding(self):
        worker = SummaryWorker()
        result = worker.summarise(["only finding"])
        assert isinstance(result, str)
        assert "1" in result


# ---------------------------------------------------------------------------
# End-to-end orchestrator tests
# ---------------------------------------------------------------------------

class TestOrchestrator:
    def setup_method(self):
        self.orchestrator = Orchestrator()

    def test_returns_expected_keys(self):
        result = self.orchestrator.run("topic A and topic B")
        assert "goal" in result
        assert "findings" in result
        assert "summary" in result

    def test_goal_preserved(self):
        goal = "neural networks and backpropagation"
        result = self.orchestrator.run(goal)
        assert result["goal"] == goal

    def test_two_findings_produced(self):
        """One research call per topic -> 2 findings total."""
        result = self.orchestrator.run("fault tolerance and consensus")
        assert len(result["findings"]) == 2

    def test_findings_are_strings(self):
        result = self.orchestrator.run("topic A and topic B")
        for finding in result["findings"]:
            assert isinstance(finding, str)
            assert len(finding) > 0

    def test_summary_is_string(self):
        result = self.orchestrator.run("topic A and topic B")
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_goal_without_and_separator(self):
        """When goal has no 'and', the secondary topic is auto-derived."""
        result = self.orchestrator.run("single topic goal")
        assert len(result["findings"]) == 2

    def test_summary_references_source_count(self):
        result = self.orchestrator.run("alpha and beta")
        assert "2" in result["summary"]
