"""
mock_responses.py — Scripted responses for AutoGen planner and executor agents.

AutoGen agents generate replies by calling their registered `reply_func`
(or by overriding `generate_reply`).  This module provides the scripted
responses that replace real LLM calls.

Design:
  - planner_reply(): called when the planner agent needs to respond.
    Returns either a structured PLAN or a TERMINATE signal.
  - executor_reply(): called when the executor agent needs to respond.
    Returns a STATUS UPDATE for each plan step, or a DONE signal.

The conversation flow:
    user_proxy → planner (create plan)
               → executor (execute step 1)
               → executor (execute step 2)
               → executor (execute step 3)
               → planner (review / approve)
               → TERMINATE
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Scripted plan (planner's first response)
# ---------------------------------------------------------------------------

PLAN = """\
PLAN:
I have analysed the task: "Research and document agent communication patterns."

Here is the execution plan:

Step 1: Research direct request-response pattern
  - Document the mechanism, typical use cases, and trade-offs.

Step 2: Research event-driven pub/sub pattern
  - Document the broker role, fan-out behaviour, and failure modes.

Step 3: Research hierarchical delegation pattern
  - Document orchestrator/worker topology, parallelism, and fault tolerance.

Please execute these steps in order and report back after each one.
"""

# ---------------------------------------------------------------------------
# Scripted executor responses (one per step)
# ---------------------------------------------------------------------------

STEP_RESPONSES: list[str] = [
    """\
STATUS UPDATE — Step 1 complete: Direct Request-Response

The agent calls its counterpart synchronously over HTTP/gRPC and waits for a
response before continuing.

Key findings:
  - Coupling: HIGH — caller must know callee's address and API schema.
  - Latency: LOWEST — no intermediary, no broker.
  - Scalability: LIMITED — vertical scaling only; caller blocks on response.
  - Best for: low-latency, point-to-point calls where both agents are stable.

Step 1 output stored. Ready for Step 2.
""",
    """\
STATUS UPDATE — Step 2 complete: Event-Driven Pub/Sub

Agents publish events to a message broker (Kafka, RabbitMQ, etc.).  Consumers
subscribe to topics and react asynchronously.

Key findings:
  - Coupling: LOW — producers and consumers don't know about each other.
  - Latency: VARIABLE — broker adds round-trip overhead (10–100 ms typical).
  - Scalability: HIGH — broker partitions allow near-linear horizontal scaling.
  - Fault tolerance: HIGH — broker buffers messages if consumer is down.
  - Best for: fan-out, audit trails, and decoupled team ownership.

Step 2 output stored. Ready for Step 3.
""",
    """\
STATUS UPDATE — Step 3 complete: Hierarchical Delegation

An orchestrator agent receives the top-level task, decomposes it into subtasks,
and fans them out to specialised worker agents.  Results are aggregated back at
the orchestrator.

Key findings:
  - Coupling: MEDIUM — workers share a task contract with the orchestrator.
  - Latency: MEDIUM — coordination overhead adds 1–3 round trips.
  - Scalability: HIGH — subtasks can run in parallel across workers.
  - Single point of failure: the orchestrator itself (mitigated by HA deployment).
  - Best for: parallelisable workloads, divide-and-conquer pipelines.

All 3 steps complete. Awaiting planner review.
""",
]

# ---------------------------------------------------------------------------
# Planner's final review response
# ---------------------------------------------------------------------------

APPROVAL = """\
REVIEW COMPLETE — All steps approved.

The executor has successfully documented all three A2A patterns:
  1. Direct Request-Response — tight coupling, lowest latency.
  2. Event-Driven Pub/Sub   — loose coupling, highest scalability.
  3. Hierarchical Delegation — balanced coupling, parallel execution.

The research is comprehensive and ready for publication.

TERMINATE
"""

# ---------------------------------------------------------------------------
# State tracking for the conversation
# ---------------------------------------------------------------------------

_step_index: int = 0
_planner_turn: int = 0


def reset_state() -> None:
    """Reset conversation state — call between test runs."""
    global _step_index, _planner_turn
    _step_index = 0
    _planner_turn = 0


def planner_reply(messages: list[dict]) -> str:
    """
    Return the planner's next scripted response.

    Turn 0: return the PLAN.
    Turn 1+: return the APPROVAL (after executor finishes all steps).
    """
    global _planner_turn
    if _planner_turn == 0:
        _planner_turn += 1
        return PLAN
    else:
        return APPROVAL


def executor_reply(messages: list[dict]) -> str:
    """
    Return the executor's next scripted response.

    Cycles through STEP_RESPONSES in order; wraps around if called more than
    expected (defensive).
    """
    global _step_index
    idx = _step_index % len(STEP_RESPONSES)
    response = STEP_RESPONSES[idx]
    _step_index += 1
    return response
