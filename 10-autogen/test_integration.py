"""
test_integration.py — pytest tests for the AutoGen group chat demo.

Tests cover:
  - Agents are built correctly (name, human_input_mode, etc.)
  - Scripted responses return expected content
  - Planner produces a plan on first call, approval on second
  - Executor cycles through 3 step responses
  - Full group chat terminates and produces a transcript with expected structure
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

import mock_responses
from agents import TERMINATE_KEYWORD, build_agents, build_group_chat
from mock_responses import executor_reply, planner_reply


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset():
    mock_responses.reset_state()


# ---------------------------------------------------------------------------
# Mock response unit tests
# ---------------------------------------------------------------------------

class TestMockResponses:
    def setup_method(self):
        _reset()

    def test_planner_first_call_returns_plan(self):
        response = planner_reply([])
        assert "PLAN" in response
        assert "Step 1" in response

    def test_planner_second_call_returns_approval(self):
        planner_reply([])   # first call
        response = planner_reply([])  # second call
        assert TERMINATE_KEYWORD in response

    def test_executor_first_call_returns_step_1(self):
        response = executor_reply([])
        assert "Step 1" in response

    def test_executor_second_call_returns_step_2(self):
        executor_reply([])  # step 1
        response = executor_reply([])
        assert "Step 2" in response

    def test_executor_third_call_returns_step_3(self):
        executor_reply([])
        executor_reply([])
        response = executor_reply([])
        assert "Step 3" in response

    def test_responses_are_non_empty(self):
        for fn in [planner_reply, executor_reply]:
            assert fn([])


# ---------------------------------------------------------------------------
# Agent structure tests
# ---------------------------------------------------------------------------

class TestAgentStructure:
    @pytest.fixture
    def agents(self):
        _reset()
        return build_agents()

    def test_returns_three_agents(self, agents):
        assert len(agents) == 3

    def test_user_proxy_name(self, agents):
        user_proxy, _, _ = agents
        assert user_proxy.name == "user_proxy"

    def test_planner_name(self, agents):
        _, planner, _ = agents
        assert planner.name == "planner"

    def test_executor_name(self, agents):
        _, _, executor = agents
        assert executor.name == "executor"

    def test_user_proxy_never_asks_human_input(self, agents):
        user_proxy, _, _ = agents
        assert user_proxy.human_input_mode == "NEVER"

    def test_planner_never_asks_human_input(self, agents):
        _, planner, _ = agents
        assert planner.human_input_mode == "NEVER"

    def test_executor_never_asks_human_input(self, agents):
        _, _, executor = agents
        assert executor.human_input_mode == "NEVER"

    def test_termination_check_triggers_on_terminate(self, agents):
        user_proxy, _, _ = agents
        # ag2 stores the termination function as _is_termination_msg
        fn = user_proxy._is_termination_msg
        assert fn({"content": "... TERMINATE"})

    def test_termination_check_ignores_normal_messages(self, agents):
        user_proxy, _, _ = agents
        fn = user_proxy._is_termination_msg
        assert not fn({"content": "Step 1 complete."})


# ---------------------------------------------------------------------------
# GroupChat structure tests
# ---------------------------------------------------------------------------

class TestGroupChatStructure:
    @pytest.fixture
    def chat_setup(self):
        _reset()
        user_proxy, planner, executor = build_agents()
        groupchat, manager = build_group_chat(user_proxy, planner, executor)
        return groupchat, manager, user_proxy, planner, executor

    def test_groupchat_has_three_agents(self, chat_setup):
        groupchat, *_ = chat_setup
        assert len(groupchat.agents) == 3

    def test_groupchat_max_round_is_positive(self, chat_setup):
        groupchat, *_ = chat_setup
        assert groupchat.max_round > 0


# ---------------------------------------------------------------------------
# End-to-end conversation test
# ---------------------------------------------------------------------------

class TestConversation:
    @pytest.fixture(scope="class")
    def conversation_result(self):
        """Run the full conversation once and return the groupchat messages."""
        mock_responses.reset_state()
        user_proxy, planner, executor = build_agents()
        groupchat, manager = build_group_chat(user_proxy, planner, executor)
        user_proxy.initiate_chat(
            recipient=manager,
            message=(
                "Research the 3 most important A2A communication patterns."
            ),
            clear_history=True,
        )
        return groupchat.messages

    def test_conversation_has_messages(self, conversation_result):
        assert len(conversation_result) > 0

    def test_conversation_terminated(self, conversation_result):
        """At least one message must contain TERMINATE."""
        contents = [m.get("content", "") for m in conversation_result]
        assert any(TERMINATE_KEYWORD in c for c in contents), (
            "TERMINATE was never sent; conversation did not end cleanly."
        )

    def test_plan_appears_in_transcript(self, conversation_result):
        contents = " ".join(m.get("content", "") for m in conversation_result)
        assert "PLAN" in contents or "Step 1" in contents

    def test_all_three_steps_appear(self, conversation_result):
        contents = " ".join(m.get("content", "") for m in conversation_result)
        for step in ["Step 1", "Step 2", "Step 3"]:
            assert step in contents, f"{step!r} not found in transcript"
