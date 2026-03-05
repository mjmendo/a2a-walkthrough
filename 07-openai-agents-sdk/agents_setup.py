"""
agents_setup.py — Agent definitions for the OpenAI Agents SDK handoff pattern.

This module faithfully reproduces the conceptual model of the OpenAI Agents SDK
(formerly Swarm) WITHOUT requiring the real SDK or an API key.  The SDK's core
ideas are:

  Agent  = {name, instructions, tools, handoffs}
  Handoff = a pointer from one agent to another; when the model decides to hand
            off, control transfers and the new agent picks up the conversation.
  Runner  = a loop that calls the current agent, checks for a handoff token,
            and switches agents if one is found.

We implement these as plain Python dataclasses so the architecture is crystal
clear — no magic, no hidden network calls.

NOTE: If you want to use the real SDK, install it with:
    pip install openai-agents
and replace the dataclasses below with real Agent(...) objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# Core abstractions (mirrors the real SDK's Agent class)
# ---------------------------------------------------------------------------

@dataclass
class Agent:
    """
    Represents a stateless AI routine.

    In the real OpenAI Agents SDK an Agent wraps a model+system-prompt and
    exposes optional `tools` (function calls) and `handoffs` (other agents it
    can delegate to).  Agents are *stateless* — all context lives in the
    conversation messages passed to the Runner.

    Attributes:
        name:         Human-readable identifier shown in traces.
        instructions: System prompt injected before every model call.
        handoffs:     Agents this agent is allowed to delegate to.
        response_fn:  Mock replacement for the real model call.
    """

    name: str
    instructions: str
    handoffs: list["Agent"] = field(default_factory=list)
    response_fn: Callable[[str], str] | None = None  # injected in agents_setup

    def __repr__(self) -> str:
        handoff_names = [a.name for a in self.handoffs]
        return f"Agent(name={self.name!r}, handoffs={handoff_names})"


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def build_agents() -> dict[str, Agent]:
    """
    Construct the three agents and wire their handoff relationships.

    Topology:
        triage_agent ──handoff──► billing_agent
                     └──handoff──► tech_agent

    The triage agent never answers domain questions directly — it always
    delegates.  This mirrors the canonical Swarm/Agents SDK tutorial pattern.
    """
    # Import here so the module is importable without the mock (unit tests mock
    # individual response_fn attributes directly).
    from mock_model import get_billing_response, get_tech_response, get_triage_response

    billing_agent = Agent(
        name="billing_agent",
        instructions=(
            "You are a billing specialist.  Help users with invoices, refunds, "
            "subscription changes, and payment questions.  Be concise and empathetic."
        ),
        handoffs=[],  # specialist agents don't hand off further
        response_fn=get_billing_response,
    )

    tech_agent = Agent(
        name="tech_agent",
        instructions=(
            "You are a technical support engineer.  Help users debug errors, "
            "configure integrations, and understand API usage.  Provide actionable steps."
        ),
        handoffs=[],
        response_fn=get_tech_response,
    )

    triage_agent = Agent(
        name="triage_agent",
        instructions=(
            "You are a triage router.  Decide whether the user's question is about "
            "billing/payments or a technical/integration issue, then hand off to the "
            "appropriate specialist.  Do NOT answer domain questions yourself."
        ),
        handoffs=[billing_agent, tech_agent],
        response_fn=get_triage_response,
    )

    return {
        "triage_agent": triage_agent,
        "billing_agent": billing_agent,
        "tech_agent": tech_agent,
    }
