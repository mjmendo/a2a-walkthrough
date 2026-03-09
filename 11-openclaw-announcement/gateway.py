"""
Pattern 11 — OpenClaw Announcement: Gateway

The Gateway is the central hub for session management and announce routing.
It models three core OpenClaw concepts:

1. Session registry   — tracks live sessions, their depth, and requester parent.
2. Announce router    — delivers announce payloads to the correct destination
                        (external → user channel, or internal → parent session).
3. Idempotency store  — prevents duplicate announces via a seen-keys set.

Session key shapes (mirroring OpenClaw exactly):
  Depth 0 (main):  agent:<agentId>:main
  Depth 1 (sub):   agent:<agentId>:subagent:<uuid>
  Depth 2 (leaf):  agent:<agentId>:subagent:<uuid>:subagent:<uuid>
  ACP session:     agent:<agentId>:acp:<uuid>
"""

import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

CYAN  = "\033[96m"
GREEN = "\033[92m"
YELLOW= "\033[93m"
RED   = "\033[91m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Session key utilities
# ---------------------------------------------------------------------------

def make_main_key(agent_id: str) -> str:
    return f"agent:{agent_id}:main"


def make_subagent_key(agent_id: str, parent_key: str) -> str:
    run_id = str(uuid.uuid4())[:8]
    # Depth-2: nest inside an existing subagent key
    if ":subagent:" in parent_key:
        return f"{parent_key}:subagent:{run_id}"
    return f"agent:{agent_id}:subagent:{run_id}"


def make_acp_key(agent_id: str) -> str:
    run_id = str(uuid.uuid4())[:8]
    return f"agent:{agent_id}:acp:{run_id}"


def get_depth(session_key: str) -> int:
    """Return nesting depth: 0=main, 1=subagent, 2=sub-subagent."""
    return session_key.count(":subagent:")


def is_acp_key(session_key: str) -> bool:
    return ":acp:" in session_key


def is_subagent_key(session_key: str) -> bool:
    return ":subagent:" in session_key


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SessionRecord:
    """Metadata the gateway keeps for every live session."""
    session_key: str
    agent_id: str
    label: str
    depth: int
    requester_key: Optional[str]          # who spawned this session
    announce_callback: Optional[Callable] # where to deliver the announce


@dataclass
class AnnouncePayload:
    """
    Structured result announcement — the message every subagent sends back
    on completion.  Models OpenClaw's internal event block precisely:

      Result   — assistant reply text (or latest toolResult if reply empty)
      Status   — derived from runtime outcome, NOT from model output
      Stats    — compact runtime/token summary
      session_key / session_id
    """
    from enum import Enum

    class Outcome(str, Enum):
        OK      = "ok"
        ERROR   = "error"
        TIMEOUT = "timeout"
        UNKNOWN = "unknown"

    child_key:    str
    child_id:     str
    label:        str
    outcome:      "AnnouncePayload.Outcome"
    result:       str           # the actual content
    status_line:  str           # human-readable status
    runtime_ms:   int
    token_stats:  str           # compact token/cost summary

    def status_from_outcome(self) -> str:
        return {
            self.Outcome.OK:      "completed successfully",
            self.Outcome.ERROR:   "failed",
            self.Outcome.TIMEOUT: "timed out",
            self.Outcome.UNKNOWN: "unknown",
        }[self.outcome]

    def format_internal_event(self) -> str:
        """
        Format the canonical internal event block that OpenClaw injects into
        the parent's conversation context.
        """
        lines = [
            f"[subagent-announce]",
            f"  source:      subagent",
            f"  child-key:   {self.child_key}",
            f"  child-id:    {self.child_id}",
            f"  label:       {self.label}",
            f"  status:      {self.status_from_outcome()}",
            f"  result:      {self.result}",
            f"  stats:       runtime={self.runtime_ms}ms  {self.token_stats}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class Gateway:
    """
    Central session registry and announce router.

    Responsibilities:
    - Register / deregister sessions.
    - Route announce payloads: external delivery for main-session requesters,
      internal injection for subagent requesters.
    - Guard against duplicate announces via idempotency keys.
    """

    def __init__(self):
        self._sessions: dict[str, SessionRecord] = {}
        self._seen_announces: set[str] = set()          # idempotency store

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def register(self, record: SessionRecord) -> None:
        self._sessions[record.session_key] = record
        print(
            f"{CYAN}[Gateway] register{RESET} "
            f"key={record.session_key}  depth={record.depth}"
        )

    def deregister(self, session_key: str) -> None:
        self._sessions.pop(session_key, None)

    def get(self, session_key: str) -> Optional[SessionRecord]:
        return self._sessions.get(session_key)

    # ------------------------------------------------------------------
    # Announce routing  (OpenClaw: runSubagentAnnounceDispatch)
    # ------------------------------------------------------------------

    def deliver_announce(
        self,
        payload: AnnouncePayload,
        idempotency_key: str,
    ) -> bool:
        """
        Route an announce payload to the requester of child_key.

        Returns True if delivered, False if duplicate.

        Delivery rules:
          - Requester is main session (depth 0):
              external delivery — invoke announce_callback with deliver=True,
              simulating sending to the user-facing channel.
          - Requester is a subagent (depth >= 1):
              internal injection — invoke announce_callback with deliver=False,
              so the orchestrator can synthesize child results in-session.
          - Fallback: if requester session is gone, walk up to its requester.
        """
        if idempotency_key in self._seen_announces:
            print(f"{YELLOW}[Gateway] duplicate announce ignored{RESET}  key={idempotency_key}")
            return False
        self._seen_announces.add(idempotency_key)

        child_record = self.get(payload.child_key)
        requester_key = child_record.requester_key if child_record else None

        requester = self.get(requester_key) if requester_key else None
        if requester is None:
            # Requester gone — walk up one level if possible
            if requester_key and ":subagent:" in requester_key:
                parent_of_requester_key = self._find_parent(requester_key)
                requester = self.get(parent_of_requester_key) if parent_of_requester_key else None

        if requester is None:
            print(f"{RED}[Gateway] announce undeliverable — requester not found{RESET}")
            return False

        deliver_external = (requester.depth == 0)
        mode = "external→user" if deliver_external else "internal→parent-session"
        print(
            f"{GREEN}[Gateway] announce delivery{RESET}  "
            f"child={payload.child_key}  requester={requester.session_key}  mode={mode}"
        )

        if requester.announce_callback:
            requester.announce_callback(payload, deliver_external)

        return True

    def _find_parent(self, session_key: str) -> Optional[str]:
        """Find the requester key of a session (walk the registry)."""
        for rec in self._sessions.values():
            if rec.session_key == session_key:
                return rec.requester_key
        return None
