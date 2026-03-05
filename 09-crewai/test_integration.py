"""
test_integration.py — pytest tests for the CrewAI A2A research crew.

Tests cover:
  - Crew can be instantiated with the mock LLM patch
  - Each agent has the correct role/goal/backstory
  - Task descriptions are non-empty and assigned to the right agents
  - Mock LLM returns different responses for different keywords
  - Crew kickoff completes and returns a non-empty result
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("OPENAI_API_KEY", "mock-key-not-used")

from crew import build_crew
from mock_llm import get_scripted_response


# ---------------------------------------------------------------------------
# MockLLM unit tests
# ---------------------------------------------------------------------------

class TestMockLLM:
    def test_research_keyword_triggers_research_script(self):
        response = get_scripted_response("research agent communication patterns")
        assert "Research Report" in response or "Pattern" in response

    def test_comparison_keyword_triggers_analysis_script(self):
        response = get_scripted_response("compare A2A patterns on coupling")
        assert "Comparative" in response or "|" in response  # table expected

    def test_summary_keyword_triggers_writing_script(self):
        response = get_scripted_response("executive summary for leadership")
        assert "Executive Summary" in response or "Recommendation" in response

    def test_unknown_prompt_returns_fallback(self):
        response = get_scripted_response("xyzzy frobble zorblax")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_responses_differ_by_keyword(self):
        r1 = get_scripted_response("research patterns")
        r2 = get_scripted_response("compare patterns")
        r3 = get_scripted_response("executive summary")
        # All three responses should be distinct
        assert r1 != r2
        assert r2 != r3
        assert r1 != r3


# ---------------------------------------------------------------------------
# Crew structure tests
# ---------------------------------------------------------------------------

class TestCrewStructure:
    @pytest.fixture(scope="class")
    def crew(self):
        return build_crew()

    def test_crew_has_three_agents(self, crew):
        assert len(crew.agents) == 3

    def test_crew_has_three_tasks(self, crew):
        assert len(crew.tasks) == 3

    def test_agent_roles(self, crew):
        roles = {a.role for a in crew.agents}
        assert "Senior Researcher" in roles
        assert "Tech Analyst" in roles
        assert "Technical Writer" in roles

    def test_agent_goals_are_non_empty(self, crew):
        for agent in crew.agents:
            assert agent.goal, f"Agent {agent.role!r} has empty goal"

    def test_agent_backstories_are_non_empty(self, crew):
        for agent in crew.agents:
            assert agent.backstory, f"Agent {agent.role!r} has empty backstory"

    def test_task_descriptions_are_non_empty(self, crew):
        for task in crew.tasks:
            assert task.description, "A task has an empty description"

    def test_task_expected_outputs_are_non_empty(self, crew):
        for task in crew.tasks:
            assert task.expected_output, "A task has an empty expected_output"

    def test_tasks_assigned_to_correct_agents(self, crew):
        """Tasks must be assigned to specific agents (not floating)."""
        for task in crew.tasks:
            assert task.agent is not None, f"Task {task.description[:40]!r} has no agent"

    def test_analyst_task_has_context(self, crew):
        """The analyst's task should have the researcher's task as context."""
        analyst_task = next(
            t for t in crew.tasks if t.agent.role == "Tech Analyst"
        )
        assert analyst_task.context, "Analyst task should have context from researcher"

    def test_writer_task_has_context(self, crew):
        writer_task = next(
            t for t in crew.tasks if t.agent.role == "Technical Writer"
        )
        assert writer_task.context, "Writer task should have context from previous tasks"


# ---------------------------------------------------------------------------
# End-to-end run test
# ---------------------------------------------------------------------------

class TestCrewExecution:
    @pytest.fixture(scope="class")
    def result(self):
        """Run the crew once; reuse the result across tests in this class."""
        crew = build_crew()
        return crew.kickoff()

    def test_kickoff_returns_result(self, result):
        assert result is not None

    def test_result_is_non_empty(self, result):
        raw = getattr(result, "raw", None) or str(result)
        assert len(raw) > 10, f"Result too short: {raw!r}"

    def test_result_contains_expected_content(self, result):
        raw = getattr(result, "raw", None) or str(result)
        # The final output is the writer's summary which mentions key concepts
        keywords = ["agent", "pattern", "communication"]
        assert any(kw.lower() in raw.lower() for kw in keywords), (
            f"Result does not mention expected keywords. Got: {raw[:200]!r}"
        )
