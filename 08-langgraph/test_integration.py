"""
test_integration.py — pytest tests for the LangGraph research pipeline.

Tests:
  - Graph compiles without error
  - Full run produces a non-empty final state
  - Each node is reachable and updates the expected state keys
  - The review→revise→draft cycle fires at least once
  - Individual node functions behave correctly in isolation
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from graph import build_graph, should_revise
from nodes import draft_node, finalize_node, research_node, review_node, revise_node
from state import ResearchState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def compiled_graph():
    """Compile the graph once for the test session."""
    return build_graph()


@pytest.fixture(scope="module")
def full_run_result(compiled_graph):
    """Run the full graph and return the final state (computed once)."""
    initial: ResearchState = {
        "topic": "agent communication patterns",
        "research": [],
        "draft": "",
        "feedback": "",
        "revision_count": 0,
        "final": "",
    }
    return compiled_graph.invoke(initial)


# ---------------------------------------------------------------------------
# Graph-level tests
# ---------------------------------------------------------------------------

class TestGraphCompilation:
    def test_graph_compiles(self, compiled_graph):
        """build_graph() must return a compiled runnable without raising."""
        assert compiled_graph is not None

    def test_graph_has_invoke_method(self, compiled_graph):
        assert callable(getattr(compiled_graph, "invoke", None))


class TestFullRun:
    def test_final_field_is_set(self, full_run_result):
        """The 'final' key must be non-empty after the graph completes."""
        assert full_run_result.get("final"), "Expected non-empty 'final' in state"

    def test_research_has_three_findings(self, full_run_result):
        research = full_run_result.get("research", [])
        assert len(research) == 3, f"Expected 3 findings, got {len(research)}"

    def test_draft_is_non_empty(self, full_run_result):
        assert full_run_result.get("draft", "")

    def test_feedback_is_non_empty(self, full_run_result):
        assert full_run_result.get("feedback", "")

    def test_revision_cycle_occurred(self, full_run_result):
        """revision_count must be > 0 — the review→revise→draft loop fired."""
        assert full_run_result.get("revision_count", 0) >= 1

    def test_final_contains_topic(self, full_run_result):
        final = full_run_result.get("final", "")
        assert "agent communication" in final.lower()

    def test_run_with_different_topic(self, compiled_graph):
        """Graph must work with an arbitrary topic string."""
        result = compiled_graph.invoke({
            "topic": "distributed systems",
            "research": [],
            "draft": "",
            "feedback": "",
            "revision_count": 0,
            "final": "",
        })
        assert result.get("final"), "Expected non-empty 'final' for alternate topic"


# ---------------------------------------------------------------------------
# Node-level unit tests
# ---------------------------------------------------------------------------

class TestResearchNode:
    def test_returns_research_key(self):
        update = research_node({"topic": "agent communication patterns"})
        assert "research" in update

    def test_returns_three_findings(self):
        update = research_node({"topic": "agent communication patterns"})
        assert len(update["research"]) == 3

    def test_findings_are_strings(self):
        update = research_node({"topic": "anything"})
        for f in update["research"]:
            assert isinstance(f, str)


class TestDraftNode:
    def test_returns_draft_key(self):
        state: ResearchState = {
            "topic": "test",
            "research": ["Finding 1", "Finding 2"],
            "revision_count": 0,
        }
        update = draft_node(state)
        assert "draft" in update

    def test_draft_is_string(self):
        state: ResearchState = {
            "topic": "test",
            "research": ["Finding 1"],
            "revision_count": 0,
        }
        update = draft_node(state)
        assert isinstance(update["draft"], str)

    def test_draft_contains_revision_notes_after_revision(self):
        state: ResearchState = {
            "topic": "test",
            "research": ["Finding 1"],
            "revision_count": 1,
        }
        update = draft_node(state)
        assert "Revision Notes" in update["draft"]


class TestReviewNode:
    def test_returns_feedback_and_revision_count(self):
        state: ResearchState = {"draft": "Some draft.", "revision_count": 0}
        update = review_node(state)
        assert "feedback" in update
        assert "revision_count" in update

    def test_first_review_requests_revision(self):
        state: ResearchState = {"draft": "Draft.", "revision_count": 0}
        update = review_node(state)
        assert update["revision_count"] == 1

    def test_second_review_approves(self):
        state: ResearchState = {"draft": "Revised draft.", "revision_count": 1}
        update = review_node(state)
        # revision_count not incremented on approval
        assert update["revision_count"] == 1


class TestReviseNode:
    def test_returns_empty_dict(self):
        """revise_node signals the loop via state; it returns no new keys."""
        state: ResearchState = {"feedback": "Please add tables.", "revision_count": 1}
        update = revise_node(state)
        assert isinstance(update, dict)


class TestFinalizeNode:
    def test_returns_final_key(self):
        state: ResearchState = {"draft": "Final draft.", "topic": "test topic"}
        update = finalize_node(state)
        assert "final" in update

    def test_final_is_non_empty(self):
        state: ResearchState = {"draft": "Draft content.", "topic": "test"}
        update = finalize_node(state)
        assert update["final"]


# ---------------------------------------------------------------------------
# Conditional edge function
# ---------------------------------------------------------------------------

class TestShouldRevise:
    def test_returns_revise_when_first_review(self):
        # After first review: revision_count=1, draft has no "Revision Notes"
        state: ResearchState = {"revision_count": 1, "draft": "A plain draft."}
        assert should_revise(state) == "revise"

    def test_returns_finalize_after_revision(self):
        # After revise→draft cycle: "Revision Notes" in draft
        state: ResearchState = {
            "revision_count": 1,
            "draft": "A draft.\n## Revision Notes (revision #1)\n...",
        }
        assert should_revise(state) == "finalize"

    def test_returns_finalize_for_high_revision_count(self):
        state: ResearchState = {"revision_count": 3, "draft": "Draft."}
        assert should_revise(state) == "finalize"
