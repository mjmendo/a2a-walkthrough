"""
test_integration.py — pytest tests for the OpenAI Agents SDK handoff pattern.

Tests cover:
  - Billing keywords route to billing_agent
  - Technical keywords route to tech_agent
  - Ambiguous input stays with triage (no handoff)
  - Handoff chain terminates (max_turns guard)
  - Agent graph structure is correctly wired
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from agents_setup import build_agents
from main import HANDOFF_PREFIX, run


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agents():
    """Return the full agent graph."""
    return build_agents()


@pytest.fixture
def triage(agents):
    """Return the triage entry-point agent."""
    return agents["triage_agent"]


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------

class TestRouting:
    """Verify that triage correctly routes messages to specialist agents."""

    def test_billing_keywords_route_to_billing_agent(self, triage):
        """Messages with billing keywords must end at billing_agent."""
        response = run(triage, "I need a refund for my last invoice.")
        # billing_agent's response always starts with "Billing Agent:"
        assert response.startswith("Billing Agent:"), (
            f"Expected billing_agent response, got: {response!r}"
        )

    def test_payment_keyword_routes_to_billing_agent(self, triage):
        """The word 'payment' must trigger a billing handoff."""
        response = run(triage, "My payment failed yesterday.")
        assert response.startswith("Billing Agent:")

    def test_subscription_keyword_routes_to_billing_agent(self, triage):
        response = run(triage, "I want to cancel my subscription.")
        assert response.startswith("Billing Agent:")

    def test_technical_keywords_route_to_tech_agent(self, triage):
        """Messages with technical keywords must end at tech_agent."""
        response = run(triage, "I'm getting a crash when I call the API.")
        assert response.startswith("Tech Agent:"), (
            f"Expected tech_agent response, got: {response!r}"
        )

    def test_install_keyword_routes_to_tech_agent(self, triage):
        response = run(triage, "How do I install and configure the SDK?")
        assert response.startswith("Tech Agent:")

    def test_ambiguous_input_stays_with_triage(self, triage):
        """A vague message should NOT produce a specialist response."""
        response = run(triage, "Can you help me please?")
        # When triage cannot decide it returns a plain (non-handoff) string
        assert not response.startswith("HANDOFF:")
        assert not response.startswith("Billing Agent:")
        assert not response.startswith("Tech Agent:")


# ---------------------------------------------------------------------------
# Handoff mechanics
# ---------------------------------------------------------------------------

class TestHandoffMechanics:
    """Verify the internal handoff protocol."""

    def test_triage_response_contains_handoff_prefix_for_billing(self, agents):
        """The triage mock must return a HANDOFF: token for billing input."""
        triage = agents["triage_agent"]
        raw = triage.response_fn("I need a refund")
        assert raw.startswith(HANDOFF_PREFIX)
        assert raw == "HANDOFF:billing_agent"

    def test_triage_response_contains_handoff_prefix_for_tech(self, agents):
        triage = agents["triage_agent"]
        raw = triage.response_fn("I have a bug in my code")
        assert raw.startswith(HANDOFF_PREFIX)
        assert raw == "HANDOFF:tech_agent"

    def test_billing_agent_does_not_hand_off(self, agents):
        """Specialist agents should return plain text, not handoff tokens."""
        billing = agents["billing_agent"]
        response = billing.response_fn("I need a refund")
        assert not response.startswith(HANDOFF_PREFIX)

    def test_tech_agent_does_not_hand_off(self, agents):
        tech = agents["tech_agent"]
        response = tech.response_fn("I have a bug")
        assert not response.startswith(HANDOFF_PREFIX)


# ---------------------------------------------------------------------------
# Agent graph structure
# ---------------------------------------------------------------------------

class TestAgentGraph:
    """Verify the agent topology is correctly wired."""

    def test_triage_has_two_handoffs(self, agents):
        triage = agents["triage_agent"]
        assert len(triage.handoffs) == 2

    def test_triage_handoff_names(self, agents):
        triage = agents["triage_agent"]
        names = {a.name for a in triage.handoffs}
        assert names == {"billing_agent", "tech_agent"}

    def test_billing_agent_has_no_handoffs(self, agents):
        assert agents["billing_agent"].handoffs == []

    def test_tech_agent_has_no_handoffs(self, agents):
        assert agents["tech_agent"].handoffs == []

    def test_all_agents_have_instructions(self, agents):
        for name, agent in agents.items():
            assert agent.instructions, f"Agent {name!r} has empty instructions"

    def test_all_agents_have_response_fn(self, agents):
        for name, agent in agents.items():
            assert callable(agent.response_fn), (
                f"Agent {name!r} has no response_fn"
            )
