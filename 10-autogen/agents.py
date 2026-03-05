"""
agents.py — AutoGen agent definitions for the plan-execute-approve demo.

AutoGen concepts shown here:
  - ConversableAgent:  the base agent class; can send/receive messages.
  - UserProxyAgent:    a special agent that represents the human (or automated
                       proxy); initiates conversations.
  - GroupChat:         a shared channel where multiple agents exchange messages.
  - GroupChatManager:  selects the next speaker and drives the conversation.
  - human_input_mode:  "NEVER" means the agent never pauses to ask a human.
  - llm_config=False:  disables the built-in LLM; we provide reply functions
                       manually via register_reply().

Conversation flow:
    user_proxy ──► planner (creates plan)
                       ──► executor (step 1)
                       ──► executor (step 2)
                       ──► executor (step 3)
                       ──► planner (reviews / approves)
                       ──► TERMINATE
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from autogen import ConversableAgent, GroupChat, GroupChatManager, UserProxyAgent

from mock_responses import executor_reply, planner_reply

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
MAGENTA = "\033[95m"
RESET   = "\033[0m"

# ---------------------------------------------------------------------------
# TERMINATE keyword (standard AutoGen convention)
# ---------------------------------------------------------------------------
TERMINATE_KEYWORD = "TERMINATE"


# ---------------------------------------------------------------------------
# Agent builders
# ---------------------------------------------------------------------------

def build_agents() -> tuple[UserProxyAgent, ConversableAgent, ConversableAgent]:
    """
    Build and return (user_proxy, planner, executor).

    We register custom reply functions that return scripted strings instead of
    calling a real LLM.  AutoGen's reply function signature is:
        fn(agent, messages, sender, config) → (bool, str | None)
    Returning (True, <string>) means "I handled this; use this string."
    Returning (False, None)  means "pass to the next reply function."
    """

    # ── user_proxy ─────────────────────────────────────────────────────────
    # UserProxyAgent initiates the conversation and checks termination.
    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",   # fully automated — no keyboard input
        max_consecutive_auto_reply=10,
        is_termination_msg=lambda msg: TERMINATE_KEYWORD in msg.get("content", ""),
        code_execution_config=False,  # disable code execution for safety
        llm_config=False,             # no LLM needed for the proxy
        system_message="You are the task initiator. Send the initial task and wait for results.",
    )

    # ── planner ────────────────────────────────────────────────────────────
    planner = ConversableAgent(
        name="planner",
        human_input_mode="NEVER",
        llm_config=False,           # LLM disabled; we use register_reply instead
        system_message=(
            "You are a planning agent. Given a task, break it into concrete steps "
            "and assign them to the executor. After all steps are done, review "
            "the results and either request revisions or send TERMINATE."
        ),
    )

    # ── executor ───────────────────────────────────────────────────────────
    executor = ConversableAgent(
        name="executor",
        human_input_mode="NEVER",
        llm_config=False,
        system_message=(
            "You are an execution agent. Carry out each step assigned by the planner "
            "and report back with a STATUS UPDATE. Do one step at a time."
        ),
    )

    # ── Register mock reply functions ──────────────────────────────────────
    # AutoGen checks registered reply functions in order.  We register our
    # mock at position 1 (after the default "no reply" check at position 0).

    def _planner_reply_fn(agent, messages, sender, config):
        # Only respond when it's actually the planner's turn
        response = planner_reply(messages)
        print(f"\n{CYAN}[planner]{RESET} → {response[:120].strip()}...")
        return True, response

    def _executor_reply_fn(agent, messages, sender, config):
        response = executor_reply(messages)
        print(f"\n{YELLOW}[executor]{RESET} → {response[:120].strip()}...")
        return True, response

    # register_reply(trigger, fn, position)
    # trigger=ConversableAgent means: fire for any ConversableAgent sender
    planner.register_reply(
        trigger=ConversableAgent,
        reply_func=_planner_reply_fn,
        position=1,
    )
    executor.register_reply(
        trigger=ConversableAgent,
        reply_func=_executor_reply_fn,
        position=1,
    )

    return user_proxy, planner, executor


def build_group_chat(
    user_proxy: UserProxyAgent,
    planner: ConversableAgent,
    executor: ConversableAgent,
) -> tuple[GroupChat, GroupChatManager]:
    """
    Build a GroupChat where user_proxy, planner, and executor collaborate.

    GroupChat manages the shared message history and speaker selection.
    GroupChatManager drives the conversation loop using a manager LLM — but
    we override it here to use a simple round-robin / custom selector.
    """

    def custom_speaker_selector(last_speaker, groupchat: GroupChat):
        """
        Deterministic speaker selection:
          - After user_proxy → planner creates the plan
          - After planner's plan → executor (steps 1, 2, 3)
          - After executor's 3rd step → planner for review
          - After planner's TERMINATE → stop
        """
        messages = groupchat.messages
        if not messages:
            return planner

        last_msg = messages[-1].get("content", "")
        last_name = last_speaker.name if last_speaker else ""

        if last_name == "user_proxy":
            return planner
        elif last_name == "planner":
            if TERMINATE_KEYWORD in last_msg:
                return None  # end conversation
            return executor  # planner just made a plan → executor
        elif last_name == "executor":
            # Count how many executor turns have happened
            executor_turns = sum(
                1 for m in messages if m.get("name") == "executor"
            )
            if executor_turns >= 3:
                return planner  # all steps done → planner reviews
            return executor   # more steps to go
        return planner

    groupchat = GroupChat(
        agents=[user_proxy, planner, executor],
        messages=[],
        max_round=12,
        speaker_selection_method=custom_speaker_selector,
    )

    # GroupChatManager needs an llm_config to select speakers — we use our
    # custom speaker_selection_method above so llm_config can be False.
    manager = GroupChatManager(
        groupchat=groupchat,
        llm_config=False,
    )

    return groupchat, manager
