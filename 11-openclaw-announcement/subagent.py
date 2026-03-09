"""
Pattern 11 — OpenClaw Announcement: Subagent Runtime + Announce Flow

This module models the subagent-side of OpenClaw's announcement pattern.

Key OpenClaw behaviours reproduced here:

1.  Non-blocking spawn — sessions_spawn returns {status, runId, childKey}
    immediately; the actual work runs in a background thread.

2.  ANNOUNCE_SKIP sentinel — if a subagent's final reply is exactly this
    string, the announce step is suppressed entirely.

3.  Outcome classification — outcome is derived from runtime signals
    (ok / error / timeout / unknown), never from model text.

4.  Announce flow (runSubagentAnnounceFlow):
      a.  Build AnnouncePayload from run result + outcome.
      b.  Attempt direct delivery to the gateway.
      c.  On transient failure: retry with exponential backoff
          (5 s → 10 s → 20 s in production; 8 ms → 16 ms → 32 ms in tests).
      d.  On permanent failure or exhausted retries: enqueue for later.

5.  Nested orchestrator support — a depth-1 subagent with maxSpawnDepth=2
    may itself spawn depth-2 worker subagents, forming:
        main (depth 0) → orchestrator (depth 1) → workers (depth 2)
    Workers announce to orchestrator (internal); orchestrator then
    announces to main (external → user).
"""

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from gateway import (
    AnnouncePayload,
    Gateway,
    SessionRecord,
    get_depth,
    make_subagent_key,
    is_acp_key,
)

ANNOUNCE_SKIP = "ANNOUNCE_SKIP"   # sentinel: suppress announce entirely

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
MAGENTA= "\033[95m"
RESET  = "\033[0m"

# Retry delays (ms) — set FAST_TEST=True to use the test-speed delays
FAST_TEST = False
RETRY_DELAYS_MS = [8, 16, 32] if FAST_TEST else [5_000, 10_000, 20_000]


# ---------------------------------------------------------------------------
# SpawnResult — what sessions_spawn returns immediately (non-blocking)
# ---------------------------------------------------------------------------

@dataclass
class SpawnResult:
    status: str           # always "accepted"
    run_id: str
    child_session_key: str


# ---------------------------------------------------------------------------
# Subagent
# ---------------------------------------------------------------------------

class Subagent:
    """
    Represents one background agent run (depth 1 or depth 2).

    The task function is executed in a background thread.  On completion the
    announce flow is triggered automatically — the parent never needs to poll.

    Parameters
    ----------
    agent_id        : agent namespace (shared with parent)
    label           : human-readable task name
    task_fn         : callable(task: str) -> str  — the actual work
                      Return ANNOUNCE_SKIP to suppress the announcement.
    gateway         : shared Gateway instance
    requester_key   : session key of the spawning session
    max_spawn_depth : depth limit; 1 = leaf only, 2 = may spawn children
    run_timeout_s   : abort run after N seconds (0 = no timeout)
    """

    def __init__(
        self,
        agent_id: str,
        label: str,
        task_fn: Callable[[str], str],
        gateway: Gateway,
        requester_key: str,
        max_spawn_depth: int = 1,
        run_timeout_s: int = 0,
    ):
        self.agent_id = agent_id
        self.label = label
        self.task_fn = task_fn
        self.gateway = gateway
        self.requester_key = requester_key
        self.max_spawn_depth = max_spawn_depth
        self.run_timeout_s = run_timeout_s

        parent_depth = get_depth(requester_key)
        self.session_key = make_subagent_key(agent_id, requester_key)
        self.session_id  = str(uuid.uuid4())[:8]
        self.depth       = get_depth(self.session_key)

        self._thread: Optional[threading.Thread] = None
        self._run_id = str(uuid.uuid4())[:8]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def spawn(self, task: str) -> SpawnResult:
        """
        Non-blocking spawn — mirrors sessions_spawn tool.

        Starts the background thread immediately and returns a SpawnResult.
        The caller does NOT need to wait; the announce will be delivered
        automatically when the run finishes.
        """
        # Register this session in the gateway
        record = SessionRecord(
            session_key=self.session_key,
            agent_id=self.agent_id,
            label=self.label,
            depth=self.depth,
            requester_key=self.requester_key,
            announce_callback=None,   # subagent delivers outbound, not inbound
        )
        self.gateway.register(record)

        print(
            f"{CYAN}[Subagent]{RESET} spawned  "
            f"key={self.session_key}  depth={self.depth}  task={task!r}"
        )

        self._thread = threading.Thread(
            target=self._run,
            args=(task,),
            daemon=True,
        )
        self._thread.start()

        return SpawnResult(
            status="accepted",
            run_id=self._run_id,
            child_session_key=self.session_key,
        )

    def join(self, timeout: float | None = None) -> None:
        """Block until the background thread (+ announce) finishes."""
        if self._thread:
            self._thread.join(timeout=timeout)

    # ------------------------------------------------------------------
    # Internal — background execution
    # ------------------------------------------------------------------

    def _run(self, task: str) -> None:
        start_ms = int(time.monotonic() * 1000)
        outcome  = AnnouncePayload.Outcome.OK
        result   = ""

        try:
            if self.run_timeout_s > 0:
                # Run with timeout via a secondary thread
                holder: list[str | Exception] = []
                t = threading.Thread(target=lambda: holder.append(self.task_fn(task)))
                t.start()
                t.join(timeout=self.run_timeout_s)
                if t.is_alive():
                    outcome = AnnouncePayload.Outcome.TIMEOUT
                    result  = f"(task timed out after {self.run_timeout_s}s)"
                else:
                    val = holder[0] if holder else ""
                    if isinstance(val, Exception):
                        raise val
                    result = str(val)
            else:
                result = str(self.task_fn(task))

        except Exception as exc:
            outcome = AnnouncePayload.Outcome.ERROR
            result  = f"(error: {exc})"
            print(f"{RED}[Subagent {self.session_key}] task error: {exc}{RESET}")

        runtime_ms = int(time.monotonic() * 1000) - start_ms
        try:
            self._run_announce_flow(result, outcome, runtime_ms)
        except Exception as exc:
            print(f"{RED}[Subagent {self.session_key}] announce flow crashed: {exc}{RESET}")

    def _run_announce_flow(
        self,
        result: str,
        outcome: AnnouncePayload.Outcome,
        runtime_ms: int,
    ) -> None:
        """
        runSubagentAnnounceFlow — the core announce logic.

        Steps:
          1. Check ANNOUNCE_SKIP sentinel.
          2. Build AnnouncePayload.
          3. Attempt direct delivery to the gateway with retries.
          4. On permanent failure: log and give up (queue not modelled here).
        """
        # Step 1 — ANNOUNCE_SKIP check
        if result.strip() == ANNOUNCE_SKIP:
            print(
                f"{YELLOW}[Subagent {self.session_key}] "
                f"ANNOUNCE_SKIP — no announce posted{RESET}"
            )
            self.gateway.deregister(self.session_key)
            return

        # Step 2 — Build payload
        token_stats = f"tokens=~{len(result.split())}"  # simplified mock stat
        status_map = {
            AnnouncePayload.Outcome.OK:      "completed successfully",
            AnnouncePayload.Outcome.ERROR:   "failed",
            AnnouncePayload.Outcome.TIMEOUT: "timed out",
            AnnouncePayload.Outcome.UNKNOWN: "unknown",
        }
        payload = AnnouncePayload(
            child_key=self.session_key,
            child_id=self.session_id,
            label=self.label,
            outcome=outcome,
            result=result,
            status_line=status_map[outcome],
            runtime_ms=runtime_ms,
            token_stats=token_stats,
        )

        idempotency_key = f"{self.session_key}:{self._run_id}"

        print(f"\n{MAGENTA}[Subagent {self.session_key}] announce flow starting{RESET}")
        print(payload.format_internal_event())

        # Step 3 — Direct delivery with retries
        delivered = self._attempt_delivery_with_retry(payload, idempotency_key)

        if not delivered:
            print(
                f"{RED}[Subagent {self.session_key}] "
                f"announce give-up (queue fallback not modelled){RESET}"
            )

        # Cleanup
        self.gateway.deregister(self.session_key)

    def _attempt_delivery_with_retry(
        self,
        payload: AnnouncePayload,
        idempotency_key: str,
    ) -> bool:
        """Deliver to gateway; retry on transient failure."""
        try:
            return self.gateway.deliver_announce(payload, idempotency_key)
        except Exception as exc:
            print(f"{YELLOW}[Subagent] direct delivery failed: {exc} — retrying{RESET}")

        for delay_ms in RETRY_DELAYS_MS:
            time.sleep(delay_ms / 1000)
            try:
                return self.gateway.deliver_announce(payload, idempotency_key)
            except Exception as exc:
                print(f"{YELLOW}[Subagent] retry failed: {exc}{RESET}")

        return False


# ---------------------------------------------------------------------------
# ACP Session (Agent Client Protocol)
# ---------------------------------------------------------------------------

class AcpSession:
    """
    Models an ACP (Agent Client Protocol) session — OpenClaw's bridge to
    external coding harnesses such as Claude Code, Codex, or Gemini CLI.

    Key differences vs. native Subagent:
      - session key uses :acp: prefix  (agent:<id>:acp:<uuid>)
      - runs externally on the host — not sandboxable
      - streamTo="parent" streams progress summaries back as system events
        instead of waiting for a final announce
      - spawn params include runtime="acp" and agentId (harness name)
    """

    def __init__(
        self,
        agent_id: str,
        harness: str,          # "claude-code", "codex", "gemini-cli", etc.
        gateway: Gateway,
        requester_key: str,
        stream_to_parent: bool = False,
    ):
        from gateway import make_acp_key
        self.session_key = make_acp_key(agent_id)
        self.session_id  = str(uuid.uuid4())[:8]
        self.harness     = harness
        self.gateway     = gateway
        self.requester_key = requester_key
        self.stream_to_parent = stream_to_parent
        self._run_id = str(uuid.uuid4())[:8]

    def spawn(self, task: str, harness_fn: Callable[[str], str]) -> SpawnResult:
        """
        Spawn an ACP harness session.  Mimics sessions_spawn with runtime="acp".
        """
        record = SessionRecord(
            session_key=self.session_key,
            agent_id=self.harness,
            label=f"acp:{self.harness}",
            depth=0,              # ACP sessions are flat; depth is irrelevant
            requester_key=self.requester_key,
            announce_callback=None,
        )
        self.gateway.register(record)

        print(
            f"{CYAN}[ACP] spawn{RESET}  "
            f"harness={self.harness}  key={self.session_key}  "
            f"stream_to_parent={self.stream_to_parent}"
        )

        t = threading.Thread(
            target=self._run,
            args=(task, harness_fn),
            daemon=True,
        )
        t.start()
        self._thread = t

        return SpawnResult(
            status="accepted",
            run_id=self._run_id,
            child_session_key=self.session_key,
        )

    def join(self) -> None:
        if self._thread:
            self._thread.join()

    def _run(self, task: str, harness_fn: Callable[[str], str]) -> None:
        if self.stream_to_parent:
            self._emit_progress("ACP harness started...")

        result = harness_fn(task)

        if self.stream_to_parent:
            self._emit_progress(f"ACP harness finished: {result}")

        self.gateway.deregister(self.session_key)

    def _emit_progress(self, msg: str) -> None:
        """
        streamTo="parent" — route progress summary back to requester session
        as a system event (not a user-visible message).
        """
        print(f"{CYAN}[ACP stream→parent]{RESET}  {msg}")
