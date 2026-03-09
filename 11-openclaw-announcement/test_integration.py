"""
Integration tests for Pattern 11 — OpenClaw Announcement.

All tests run in-process with no network or external dependencies.
Tests cover all three sub-patterns:
  A) Simple subagent + announcement
  B) Nested orchestrator (depth 1 → depth 2)
  C) ACP session with streamTo=parent
"""

import threading
import time
import pytest

from gateway import (
    AnnouncePayload,
    Gateway,
    SessionRecord,
    get_depth,
    make_main_key,
    make_subagent_key,
    make_acp_key,
    is_acp_key,
    is_subagent_key,
)
from subagent import ANNOUNCE_SKIP, AcpSession, Subagent, SpawnResult
from main_agent import MainAgent, _research_task, _mock_harness_task


# ---------------------------------------------------------------------------
# Session Key utilities
# ---------------------------------------------------------------------------

class TestSessionKeys:
    def test_main_key_format(self):
        key = make_main_key("bob")
        assert key == "agent:bob:main"

    def test_subagent_key_depth1(self):
        key = make_subagent_key("bob", "agent:bob:main")
        assert key.startswith("agent:bob:subagent:")
        assert get_depth(key) == 1

    def test_subagent_key_depth2(self):
        parent = make_subagent_key("bob", "agent:bob:main")
        child  = make_subagent_key("bob", parent)
        assert get_depth(child) == 2
        assert parent in child

    def test_acp_key_format(self):
        key = make_acp_key("bob")
        assert ":acp:" in key
        assert is_acp_key(key)
        assert not is_subagent_key(key)

    def test_depth_main(self):
        assert get_depth("agent:main:main") == 0

    def test_depth_subagent(self):
        key = make_subagent_key("x", "agent:x:main")
        assert get_depth(key) == 1


# ---------------------------------------------------------------------------
# AnnouncePayload
# ---------------------------------------------------------------------------

class TestAnnouncePayload:
    def _make(self, outcome=AnnouncePayload.Outcome.OK, result="hello") -> AnnouncePayload:
        p = AnnouncePayload(
            child_key="agent:x:subagent:abc",
            child_id="abc",
            label="test",
            outcome=outcome,
            result=result,
            status_line="",
            runtime_ms=100,
            token_stats="tokens=5",
        )
        p.status_line = p.status_from_outcome()
        return p

    def test_ok_status(self):
        assert self._make(AnnouncePayload.Outcome.OK).status_from_outcome() == "completed successfully"

    def test_error_status(self):
        assert self._make(AnnouncePayload.Outcome.ERROR).status_from_outcome() == "failed"

    def test_timeout_status(self):
        assert self._make(AnnouncePayload.Outcome.TIMEOUT).status_from_outcome() == "timed out"

    def test_format_internal_event_contains_key_fields(self):
        p = self._make(result="my result")
        event = p.format_internal_event()
        assert "subagent-announce" in event
        assert "my result" in event
        assert "completed successfully" in event


# ---------------------------------------------------------------------------
# Gateway — idempotency
# ---------------------------------------------------------------------------

class TestGateway:
    def setup_method(self):
        self.gw = Gateway()
        self.received: list[AnnouncePayload] = []

        # Register a main session
        rec = SessionRecord(
            session_key="agent:t:main",
            agent_id="t",
            label="main",
            depth=0,
            requester_key=None,
            announce_callback=lambda p, deliver: self.received.append(p),
        )
        self.gw.register(rec)

    def _child_payload(self, child_key="agent:t:subagent:xyz") -> AnnouncePayload:
        rec = SessionRecord(
            session_key=child_key,
            agent_id="t",
            label="child",
            depth=1,
            requester_key="agent:t:main",
            announce_callback=None,
        )
        self.gw.register(rec)
        p = AnnouncePayload(
            child_key=child_key,
            child_id="xyz",
            label="child",
            outcome=AnnouncePayload.Outcome.OK,
            result="done",
            status_line="completed successfully",
            runtime_ms=50,
            token_stats="tokens=3",
        )
        return p

    def test_deliver_announce_reaches_callback(self):
        payload = self._child_payload()
        delivered = self.gw.deliver_announce(payload, "key-1")
        assert delivered is True
        assert len(self.received) == 1
        assert self.received[0].result == "done"

    def test_duplicate_announce_suppressed(self):
        payload = self._child_payload()
        self.gw.deliver_announce(payload, "key-dup")
        self.gw.deliver_announce(payload, "key-dup")  # duplicate
        assert len(self.received) == 1

    def test_different_idempotency_keys_both_delivered(self):
        p1 = self._child_payload("agent:t:subagent:aaa")
        p2 = self._child_payload("agent:t:subagent:bbb")
        self.gw.deliver_announce(p1, "key-A")
        self.gw.deliver_announce(p2, "key-B")
        assert len(self.received) == 2


# ---------------------------------------------------------------------------
# Pattern A — Simple Subagent
# ---------------------------------------------------------------------------

class TestPatternA:
    def test_spawn_returns_immediately(self):
        """spawn() must be non-blocking."""
        gw = Gateway()
        received = []
        rec = SessionRecord(
            session_key="agent:a:main",
            agent_id="a",
            label="main",
            depth=0,
            requester_key=None,
            announce_callback=lambda p, d: received.append(p),
        )
        gw.register(rec)

        slow_done = threading.Event()

        def slow_task(t: str) -> str:
            slow_done.wait()
            return "slow result"

        sub = Subagent("a", "slow", slow_task, gw, "agent:a:main")
        t0 = time.monotonic()
        sub.spawn("do something")
        elapsed = time.monotonic() - t0

        # spawn() should return well before the task finishes
        assert elapsed < 0.5

        slow_done.set()
        sub.join()
        assert received[0].result == "slow result"

    def test_announce_payload_fields(self):
        agent = MainAgent()
        results = agent.run_pattern_a()
        assert len(results) == 1
        p = results[0]
        assert p.outcome == AnnouncePayload.Outcome.OK
        assert p.status_line == "completed successfully"
        assert len(p.result) > 0
        assert p.runtime_ms >= 0

    def test_announce_skip_suppresses_delivery(self):
        gw = Gateway()
        received = []
        rec = SessionRecord(
            session_key="agent:s:main",
            agent_id="s",
            label="main",
            depth=0,
            requester_key=None,
            announce_callback=lambda p, d: received.append(p),
        )
        gw.register(rec)

        sub = Subagent("s", "skip", lambda t: ANNOUNCE_SKIP, gw, "agent:s:main")
        sub.spawn("anything")
        sub.join()
        assert received == []

    def test_error_task_yields_error_outcome(self):
        gw = Gateway()
        received = []
        rec = SessionRecord(
            session_key="agent:e:main",
            agent_id="e",
            label="main",
            depth=0,
            requester_key=None,
            announce_callback=lambda p, d: received.append(p),
        )
        gw.register(rec)

        def failing_task(t: str) -> str:
            raise ValueError("boom")

        sub = Subagent("e", "fail", failing_task, gw, "agent:e:main")
        sub.spawn("anything")
        sub.join()

        assert received[0].outcome == AnnouncePayload.Outcome.ERROR
        assert "boom" in received[0].result

    def test_timeout_outcome(self):
        gw = Gateway()
        received = []
        rec = SessionRecord(
            session_key="agent:to:main",
            agent_id="to",
            label="main",
            depth=0,
            requester_key=None,
            announce_callback=lambda p, d: received.append(p),
        )
        gw.register(rec)

        def hanging_task(t: str) -> str:
            time.sleep(10)
            return "never"

        sub = Subagent("to", "hang", hanging_task, gw, "agent:to:main", run_timeout_s=1)
        sub.spawn("hang")
        sub.join()  # task times out after 1s; announce follows; total < 3s

        assert len(received) == 1
        assert received[0].outcome == AnnouncePayload.Outcome.TIMEOUT


# ---------------------------------------------------------------------------
# Pattern B — Nested Orchestrator
# ---------------------------------------------------------------------------

class TestPatternB:
    def test_nested_orchestrator_delivers_single_announce_to_main(self):
        """
        Main receives exactly one announce (from the orchestrator),
        not two (from the individual workers).
        """
        agent = MainAgent()
        results = agent.run_pattern_b()
        # Only the orchestrator's synthesised result reaches main
        assert len(results) == 1

    def test_orchestrator_result_contains_synthesis(self):
        agent = MainAgent()
        results = agent.run_pattern_b()
        assert "Synthesised" in results[0].result
        assert "2 findings" in results[0].result

    def test_depth2_worker_keys(self):
        """Workers must have depth=2 keys nested under depth=1."""
        parent = make_subagent_key("main", "agent:main:main")
        child  = make_subagent_key("main", parent)
        assert get_depth(parent) == 1
        assert get_depth(child)  == 2
        assert parent in child


# ---------------------------------------------------------------------------
# Pattern C — ACP Session
# ---------------------------------------------------------------------------

class TestPatternC:
    def test_acp_session_key_format(self):
        gw = Gateway()
        rec = SessionRecord(
            session_key="agent:c:main",
            agent_id="c",
            label="main",
            depth=0,
            requester_key=None,
            announce_callback=None,
        )
        gw.register(rec)
        acp = AcpSession("c", "codex", gw, "agent:c:main", stream_to_parent=False)
        assert is_acp_key(acp.session_key)
        assert ":acp:" in acp.session_key

    def test_acp_spawn_returns_accepted(self):
        gw = Gateway()
        rec = SessionRecord(
            session_key="agent:c2:main",
            agent_id="c2",
            label="main",
            depth=0,
            requester_key=None,
            announce_callback=None,
        )
        gw.register(rec)
        acp = AcpSession("c2", "claude-code", gw, "agent:c2:main")
        result = acp.spawn("task", lambda t: "done")
        assert result.status == "accepted"
        acp.join()

    def test_acp_runs_harness_task(self):
        gw = Gateway()
        done = threading.Event()
        outputs = []

        rec = SessionRecord(
            session_key="agent:c3:main",
            agent_id="c3",
            label="main",
            depth=0,
            requester_key=None,
            announce_callback=None,
        )
        gw.register(rec)

        def harness(t: str) -> str:
            outputs.append(t)
            done.set()
            return "harness output"

        acp = AcpSession("c3", "codex", gw, "agent:c3:main", stream_to_parent=True)
        acp.spawn("write tests", harness)
        acp.join()

        assert done.is_set()
        assert "write tests" in outputs[0]
