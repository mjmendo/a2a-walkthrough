"""
mock_llm.py — A mock LLM compatible with CrewAI's LLM interface.

CrewAI accepts any object that implements a `call` method (or a LangChain-style
BaseLLM / BaseChatModel).  In recent versions of crewai (>= 0.80) agents accept
an `llm` parameter that can be any callable or LLM object.

This module provides:
  1. MockLLM — a minimal class that matches CrewAI's expected LLM interface.
  2. Scripted responses keyed by task keyword, so each crew member "answers"
     differently depending on which task it is executing.

No real model is called.  No API key is needed.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Scripted response corpus
# ---------------------------------------------------------------------------
# Keys are substrings to match against the prompt (case-insensitive).
# The FIRST matching entry wins.
SCRIPTS: list[tuple[str, str]] = [
    # Research task
    (
        "research",
        """## Research Report: Agent-to-Agent (A2A) Communication Patterns

### Pattern 1: Direct Request-Response
**Coupling**: High  **Latency**: Low  **Scalability**: Limited
The caller invokes the callee synchronously over HTTP/gRPC.  Simple to implement
and trace, but tightly coupled — the caller must know the callee's address and schema.
Best for: low-latency, point-to-point integrations with stable interfaces.

### Pattern 2: Event-Driven (Pub/Sub)
**Coupling**: Low  **Latency**: Variable  **Scalability**: High
Agents publish events to a broker (Kafka, RabbitMQ); other agents subscribe.
Decouples producers from consumers — neither needs to know about the other.
Best for: fan-out, audit trails, and resilience to partial failures.

### Pattern 3: Hierarchical Delegation
**Coupling**: Medium  **Latency**: Medium  **Scalability**: High
An orchestrator decomposes tasks into subtasks and fans them to worker agents.
Results are aggregated back at the orchestrator.
Best for: parallel workloads that can be decomposed into independent subtasks.
""",
    ),
    # Analysis task
    (
        "compar",
        """## Comparative Analysis: A2A Patterns

| Dimension        | Direct Request-Response | Event-Driven Pub/Sub | Hierarchical Delegation |
|------------------|------------------------|----------------------|------------------------|
| **Coupling**     | Tight (address + schema) | Loose (topic only)   | Medium (task contract) |
| **Latency**      | Lowest (<10 ms)         | Higher (broker RTT)  | Medium (coordination)  |
| **Scalability**  | Vertical only           | Near-linear          | Near-linear            |
| **Complexity**   | Low                     | High (broker ops)    | Medium                 |
| **Fault tolerance** | Caller fails if callee down | Broker buffers messages | Orchestrator is SPOF |
| **Observability** | Trivial (1:1 trace)    | Requires correlation | Distributed trace      |

### Recommendation Matrix
- **Prototype / small team**: Direct Request-Response — lowest ops overhead.
- **High-throughput / decoupled teams**: Event-Driven — worth the broker cost.
- **Parallel computation**: Hierarchical Delegation — best time-to-completion.
""",
    ),
    # Writing / summary task
    (
        "summary",
        """## Executive Summary: Agent Communication Patterns

Modern distributed AI systems rely on three foundational patterns for agent
coordination, each representing a different trade-off on the coupling-latency-
scalability spectrum.

**Direct Request-Response** delivers the lowest latency and simplest debugging
experience, making it ideal for tightly integrated services where both agents
are under the same team's control and uptime is guaranteed.

**Event-Driven Pub/Sub** maximises decoupling and horizontal scalability at the
cost of operational complexity (broker management, message ordering guarantees,
dead-letter queues). It is the right choice when producers and consumers evolve
independently or when fan-out to many subscribers is required.

**Hierarchical Delegation** strikes a pragmatic middle ground: an orchestrator
agent coordinates specialised workers, enabling parallelism while keeping the
coordination logic centralised and auditable.

*Recommendation*: begin with Direct Request-Response, migrate to Hierarchical
Delegation as the workload grows, and introduce Event-Driven patterns only when
decoupling between teams or systems becomes a bottleneck.
""",
    ),
    # Generic fallback
    (
        "",
        "I have completed my assigned task and produced the required output.",
    ),
]


def _scripted_response(prompt: str) -> str:
    """Return the first matching scripted response for the given prompt."""
    lower = prompt.lower()
    for keyword, response in SCRIPTS:
        if keyword in lower:
            return response
    # Fallback: last entry always matches (empty keyword)
    return SCRIPTS[-1][1]


# ---------------------------------------------------------------------------
# MockLLM class
# ---------------------------------------------------------------------------

class MockLLM:
    """
    Minimal mock LLM compatible with CrewAI's agent `llm` parameter.

    CrewAI (>= 0.80) passes prompts to the LLM via its internal LiteLLM
    integration.  To bypass that, we patch at the agent level by overriding
    the agent's `execute_task` method in crew.py instead of injecting this
    class directly — see crew.py for details.

    This class is kept here for documentation purposes and is also used by
    test_integration.py to verify scripted responses directly.
    """

    model: str = "mock-llm-v1"

    def __call__(self, prompt: str, **kwargs: Any) -> str:
        """Callable interface — some integrations call the LLM directly."""
        return _scripted_response(prompt)

    def call(self, prompt: str, **kwargs: Any) -> str:
        """Named method interface used by some LangChain-compatible wrappers."""
        return _scripted_response(prompt)

    def generate(self, prompts: list[str], **kwargs: Any) -> Any:
        """Batch generation interface."""

        class FakeGeneration:
            text: str

        class FakeResult:
            generations: list

        results = []
        for p in prompts:
            gen = FakeGeneration()
            gen.text = _scripted_response(p)
            results.append([gen])

        result = FakeResult()
        result.generations = results
        return result

    # CrewAI 0.80+ uses LiteLLM under the hood; it checks for these attributes.
    supports_stop_words: bool = False
    metadata: dict = {}


# Convenience singleton
mock_llm = MockLLM()


# Public API used by test_integration.py
def get_scripted_response(prompt: str) -> str:
    """Return the scripted response for a given prompt string."""
    return _scripted_response(prompt)
