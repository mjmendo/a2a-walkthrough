"""
Integration tests for Pattern 4: Blackboard.

Uses fakeredis — no real Redis instance required.
Tests cover the Blackboard class and each agent in isolation and as a pipeline.
"""

import json

import fakeredis
import pytest

from agents import OutlineAgent, ReviewerAgent, WriterAgent
from blackboard import Blackboard


@pytest.fixture
def bb():
    """Provide a fresh Blackboard backed by an in-memory FakeRedis."""
    r = fakeredis.FakeRedis(decode_responses=True)
    board = Blackboard(r)
    yield board
    board.clear()


# ---------------------------------------------------------------------------
# Blackboard class unit tests
# ---------------------------------------------------------------------------

class TestBlackboard:
    def test_write_and_read(self, bb):
        bb.write("foo", "bar")
        assert bb.read("foo") == "bar"

    def test_read_missing_key_returns_none(self, bb):
        assert bb.read("nonexistent") is None

    def test_read_all_empty(self, bb):
        assert bb.read_all() == {}

    def test_read_all_multiple_keys(self, bb):
        bb.write("a", "1")
        bb.write("b", "2")
        result = bb.read_all()
        assert result["a"] == "1"
        assert result["b"] == "2"

    def test_set_and_get_status(self, bb):
        bb.set_status("outline", "done")
        assert bb.get_status("outline") == "done"

    def test_get_status_missing_returns_none(self, bb):
        assert bb.get_status("missing") is None

    def test_clear_removes_content_and_status(self, bb):
        bb.write("topic", "test")
        bb.set_status("topic", "seeded")
        bb.clear()
        assert bb.read("topic") is None
        assert bb.get_status("topic") is None

    def test_overwrite_value(self, bb):
        bb.write("key", "first")
        bb.write("key", "second")
        assert bb.read("key") == "second"


# ---------------------------------------------------------------------------
# Agent unit tests
# ---------------------------------------------------------------------------

class TestOutlineAgent:
    def test_writes_outline(self, bb):
        bb.write("topic", "machine learning")
        OutlineAgent(bb).run()
        outline_raw = bb.read("outline")
        assert outline_raw is not None
        sections = json.loads(outline_raw)
        assert isinstance(sections, list)
        assert len(sections) > 0

    def test_outline_status_done(self, bb):
        bb.write("topic", "blockchain")
        OutlineAgent(bb).run()
        assert bb.get_status("outline") == "done"

    def test_raises_if_topic_missing(self, bb):
        with pytest.raises(ValueError, match="topic"):
            OutlineAgent(bb).run()

    def test_sections_are_strings(self, bb):
        bb.write("topic", "quantum computing")
        OutlineAgent(bb).run()
        sections = json.loads(bb.read("outline"))
        for s in sections:
            assert isinstance(s, str)
            assert len(s) > 0


class TestWriterAgent:
    def _seed_outline(self, bb: Blackboard) -> None:
        bb.write("topic", "test topic")
        OutlineAgent(bb).run()

    def test_writes_draft(self, bb):
        self._seed_outline(bb)
        WriterAgent(bb).run()
        draft = bb.read("draft")
        assert draft is not None
        assert len(draft) > 0

    def test_draft_status_done(self, bb):
        self._seed_outline(bb)
        WriterAgent(bb).run()
        assert bb.get_status("draft") == "done"

    def test_draft_contains_section_headers(self, bb):
        self._seed_outline(bb)
        WriterAgent(bb).run()
        draft = bb.read("draft")
        assert "##" in draft

    def test_raises_if_outline_missing(self, bb):
        with pytest.raises(ValueError, match="outline"):
            WriterAgent(bb).run()


class TestReviewerAgent:
    def _seed_draft(self, bb: Blackboard) -> None:
        bb.write("topic", "neural networks")
        OutlineAgent(bb).run()
        WriterAgent(bb).run()

    def test_writes_review(self, bb):
        self._seed_draft(bb)
        ReviewerAgent(bb).run()
        review = bb.read("review")
        assert review is not None
        assert len(review) > 0

    def test_review_status_done(self, bb):
        self._seed_draft(bb)
        ReviewerAgent(bb).run()
        assert bb.get_status("review") == "done"

    def test_review_contains_status_line(self, bb):
        self._seed_draft(bb)
        ReviewerAgent(bb).run()
        review = bb.read("review")
        assert "STATUS:" in review

    def test_raises_if_draft_missing(self, bb):
        with pytest.raises(ValueError, match="draft"):
            ReviewerAgent(bb).run()


# ---------------------------------------------------------------------------
# Full pipeline test
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_end_to_end(self, bb):
        topic = "distributed systems"
        bb.write("topic", topic)
        bb.set_status("topic", "seeded")

        OutlineAgent(bb).run()
        WriterAgent(bb).run()
        ReviewerAgent(bb).run()

        # All keys present
        all_content = bb.read_all()
        assert "topic" in all_content
        assert "outline" in all_content
        assert "draft" in all_content
        assert "review" in all_content

        # All statuses are "done" (except topic which stays "seeded")
        assert bb.get_status("outline") == "done"
        assert bb.get_status("draft") == "done"
        assert bb.get_status("review") == "done"

        # Review makes a final verdict
        review = bb.read("review")
        assert "APPROVED" in review or "NEEDS_REVISION" in review
