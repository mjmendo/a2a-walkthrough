"""
Pattern 11 — OpenClaw Announcement: Main Agent

Demonstrates three OpenClaw interoperability patterns in one runnable script:

──────────────────────────────────────────────────────────────────────────────
Pattern A — Simple Subagent + Announcement
──────────────────────────────────────────────────────────────────────────────
  Main agent spawns one subagent (non-blocking).
  Subagent runs its task in a background thread.
  On completion, subagent announces result back to the main agent's channel.

  Delivery path:
    Subagent → Gateway.deliver_announce(deliver=True) → main agent callback

──────────────────────────────────────────────────────────────────────────────
Pattern B — Nested Orchestrator (maxSpawnDepth=2)
──────────────────────────────────────────────────────────────────────────────
  Main (depth 0) spawns an orchestrator subagent (depth 1).
  Orchestrator spawns two worker sub-subagents (depth 2).
  Workers announce to orchestrator (internal injection, deliver=False).
  Orchestrator synthesises and announces to main (external, deliver=True).

  Session key shapes:
    depth 0: agent:main:main
    depth 1: agent:main:subagent:<uuid>
    depth 2: agent:main:subagent:<uuid>:subagent:<uuid>

──────────────────────────────────────────────────────────────────────────────
Pattern C — ACP Session (Agent Client Protocol)
──────────────────────────────────────────────────────────────────────────────
  Main agent spawns an ACP session for an external harness (e.g. Claude Code).
  streamTo="parent" streams progress updates back as system events.
  The harness runs independently; its session key uses :acp: prefix.
"""

import threading
import time
from typing import Optional

from gateway import (
    AnnouncePayload,
    Gateway,
    SessionRecord,
    make_main_key,
)
from subagent import AcpSession, SpawnResult, Subagent

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
MAGENTA= "\033[95m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ---------------------------------------------------------------------------
# Main Agent
# ---------------------------------------------------------------------------

class MainAgent:
    """
    The top-level agent (depth 0).

    Spawns subagents, receives their announcements, and delivers
    user-facing replies.
    """

    def __init__(self, agent_id: str = "main"):
        self.agent_id    = agent_id
        self.session_key = make_main_key(agent_id)
        self.gateway     = Gateway()
        self._received:  list[AnnouncePayload] = []
        self._lock       = threading.Lock()

        # Register self in the gateway so subagents can find us
        record = SessionRecord(
            session_key=self.session_key,
            agent_id=self.agent_id,
            label="main",
            depth=0,
            requester_key=None,
            announce_callback=self._on_announce,
        )
        self.gateway.register(record)

    def _on_announce(self, payload: AnnouncePayload, deliver: bool) -> None:
        """
        Called by the gateway when a child announce arrives.

        deliver=True  → external delivery (user-facing reply).
        deliver=False → internal injection (orchestrator synthesis context).
        """
        with self._lock:
            self._received.append(payload)

        tag   = f"{GREEN}[user-facing]{RESET}" if deliver else f"{YELLOW}[internal]{RESET}"
        print(
            f"\n{BOLD}[MainAgent]{RESET} announce received {tag}\n"
            f"  from:    {payload.child_key}\n"
            f"  label:   {payload.label}\n"
            f"  status:  {payload.status_line}\n"
            f"  result:  {payload.result}\n"
        )

    # ------------------------------------------------------------------
    # Pattern A — Simple Subagent
    # ------------------------------------------------------------------

    def run_pattern_a(self) -> list[AnnouncePayload]:
        """Spawn one subagent and wait for its announce."""
        print(f"\n{CYAN}{'='*60}{RESET}")
        print(f"{CYAN}  PATTERN A — Simple Subagent + Announcement{RESET}")
        print(f"{CYAN}{'='*60}{RESET}\n")

        subagent = Subagent(
            agent_id=self.agent_id,
            label="research-agent",
            task_fn=_research_task,
            gateway=self.gateway,
            requester_key=self.session_key,
        )
        result: SpawnResult = subagent.spawn("distributed systems fault tolerance")

        print(f"[MainAgent] spawn returned immediately: {result}\n")

        # Non-blocking: main agent is free to do other work here
        subagent.join()

        return list(self._received)

    # ------------------------------------------------------------------
    # Pattern B — Nested Orchestrator (depth 1 → depth 2)
    # ------------------------------------------------------------------

    def run_pattern_b(self) -> list[AnnouncePayload]:
        """Spawn an orchestrator that itself spawns two workers."""
        print(f"\n{CYAN}{'='*60}{RESET}")
        print(f"{CYAN}  PATTERN B — Nested Orchestrator (maxSpawnDepth=2){RESET}")
        print(f"{CYAN}{'='*60}{RESET}\n")

        self._received.clear()

        orchestrator = Subagent(
            agent_id=self.agent_id,
            label="orchestrator",
            task_fn=self._orchestrator_task,
            gateway=self.gateway,
            requester_key=self.session_key,
            max_spawn_depth=2,
        )
        orchestrator.spawn("analyse consensus algorithms and fault tolerance")
        orchestrator.join()

        return list(self._received)

    def _orchestrator_task(self, task: str) -> str:
        """
        Depth-1 orchestrator: spawns two depth-2 workers in parallel,
        waits for their announces (injected internally), then synthesises.

        This runs inside a Subagent thread, so self here is MainAgent.
        We need to register a temporary orchestrator session so workers
        can find their requester.
        """
        # The orchestrator's session key is the current thread's subagent key.
        # We identify it by finding the most recently registered depth-1 session.
        orch_key = self._find_latest_depth1_key()
        if not orch_key:
            return "error: orchestrator key not found"

        # Register orchestrator's announce callback so workers can deliver to it
        orch_received: list[AnnouncePayload] = []
        orch_lock = threading.Lock()

        def orch_on_announce(payload: AnnouncePayload, deliver: bool) -> None:
            with orch_lock:
                orch_received.append(payload)
            print(
                f"  {YELLOW}[Orchestrator] worker announce received{RESET}  "
                f"from={payload.child_key}  result={payload.result!r}"
            )

        record = self.gateway.get(orch_key)
        if record:
            record.announce_callback = orch_on_announce

        topics = task.split(" and ", maxsplit=1)
        topic_a = topics[0].strip()
        topic_b = topics[1].strip() if len(topics) > 1 else task

        # Spawn two depth-2 workers (parallel)
        worker_a = Subagent(
            agent_id=self.agent_id,
            label=f"worker:{topic_a[:20]}",
            task_fn=_research_task,
            gateway=self.gateway,
            requester_key=orch_key,
        )
        worker_b = Subagent(
            agent_id=self.agent_id,
            label=f"worker:{topic_b[:20]}",
            task_fn=_research_task,
            gateway=self.gateway,
            requester_key=orch_key,
        )

        worker_a.spawn(topic_a)
        worker_b.spawn(topic_b)
        worker_a.join()
        worker_b.join()

        # Synthesise worker results
        findings = [p.result for p in orch_received]
        synthesis = f"Synthesised {len(findings)} findings: " + " | ".join(findings)
        print(f"  {MAGENTA}[Orchestrator] synthesis complete → announcing to main{RESET}")
        return synthesis

    def _find_latest_depth1_key(self) -> Optional[str]:
        """Locate the most recently registered depth-1 session key."""
        for key, rec in reversed(list(self.gateway._sessions.items())):
            if rec.depth == 1 and rec.requester_key == self.session_key:
                return key
        return None

    # ------------------------------------------------------------------
    # Pattern C — ACP Session
    # ------------------------------------------------------------------

    def run_pattern_c(self) -> None:
        """Spawn an ACP harness session with streamTo=parent."""
        print(f"\n{CYAN}{'='*60}{RESET}")
        print(f"{CYAN}  PATTERN C — ACP Session (External Harness){RESET}")
        print(f"{CYAN}{'='*60}{RESET}\n")

        acp = AcpSession(
            agent_id=self.agent_id,
            harness="claude-code",
            gateway=self.gateway,
            requester_key=self.session_key,
            stream_to_parent=True,
        )
        result = acp.spawn("refactor the authentication module", _mock_harness_task)
        print(f"[MainAgent] ACP spawn returned: {result}\n")
        acp.join()
        print(f"[MainAgent] ACP session complete.\n")


# ---------------------------------------------------------------------------
# Simulated task functions (no real LLM required)
# ---------------------------------------------------------------------------

def _research_task(topic: str) -> str:
    """Simulate a research subagent."""
    time.sleep(0.05)   # simulate work
    return f"Research finding on '{topic}': key insight about {topic.split()[-1]} stability"


def _mock_harness_task(task: str) -> str:
    """Simulate an external coding harness (e.g. Claude Code)."""
    time.sleep(0.05)
    return f"Harness completed: {task[:40]}... [diff: 3 files changed]"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    agent = MainAgent()

    print(f"\n{BOLD}Running Pattern A — Simple Subagent{RESET}")
    a_results = agent.run_pattern_a()
    print(f"[Main] Pattern A done — {len(a_results)} announce(s) received\n")

    print(f"\n{BOLD}Running Pattern B — Nested Orchestrator{RESET}")
    b_results = agent.run_pattern_b()
    print(f"[Main] Pattern B done — {len(b_results)} announce(s) received\n")

    print(f"\n{BOLD}Running Pattern C — ACP Session{RESET}")
    agent.run_pattern_c()
    print(f"[Main] Pattern C done\n")
