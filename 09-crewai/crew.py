"""
crew.py — CrewAI crew definition for the A2A patterns research pipeline.

CrewAI concepts demonstrated:
  - Agent: a crew member with role, goal, and backstory (persona + purpose).
  - Task:  a unit of work assigned to an agent, with expected_output defined.
  - Crew:  orchestrates agents + tasks, runs them in sequence or parallel.
  - Process.sequential: tasks execute one after another; each task's output is
    available as context for the next.

Mocking strategy
----------------
CrewAI uses LiteLLM internally (since v0.70+).  The simplest way to avoid real
API calls is to:
  1. Set OPENAI_API_KEY to a dummy value (suppresses the "missing key" error).
  2. Monkey-patch the agent's `execute_task` method to return scripted strings
     instead of calling the real LLM.
This approach works regardless of the crewai version.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Suppress "no API key" warnings before importing crewai
os.environ.setdefault("OPENAI_API_KEY", "mock-key-not-used")

from crewai import Agent, Crew, Process, Task

from mock_llm import get_scripted_response

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
MAGENTA = "\033[95m"
RESET   = "\033[0m"
BOLD    = "\033[1m"


# ---------------------------------------------------------------------------
# Mock execution patch
# ---------------------------------------------------------------------------

def _make_mock_execute(agent_name: str, task_keyword: str):
    """
    Return a replacement execute_task that returns a scripted response.

    We patch at the agent instance level so only our agents are affected.
    Each agent gets a closure over its own keyword so the responses differ.
    """
    def mock_execute_task(task, context=None, tools=None):  # type: ignore[override]
        # Build a minimal "prompt" from the task description so our keyword
        # matching in mock_llm picks the right script.
        prompt = f"{task_keyword} {task.description}"
        response = get_scripted_response(prompt)
        print(
            f"\n{CYAN}[{agent_name}]{RESET} executing task: "
            f"{task.description[:60]}..."
        )
        print(f"{GREEN}Output ({len(response)} chars):{RESET}")
        print(response[:300] + ("..." if len(response) > 300 else ""))
        return response

    return mock_execute_task


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

def build_crew() -> Crew:
    """
    Construct the three-agent crew and the three sequential tasks.

    Returns a Crew instance ready to be kicked off.
    """
    # ── Agents ─────────────────────────────────────────────────────────────
    # CrewAI agents have: role, goal, backstory, verbose flag, llm (optional)
    # The role/goal/backstory are injected into the system prompt automatically.

    researcher = Agent(
        role="Senior Researcher",
        goal="Research and document the 3 most important agent-to-agent communication patterns",
        backstory=(
            "You are an expert in distributed systems with 10 years of experience "
            "designing microservice architectures.  You are thorough, citation-driven, "
            "and always provide concrete examples."
        ),
        verbose=True,
        allow_delegation=False,
        llm="gpt-4o-mini",  # will be bypassed by the mock below
    )

    analyst = Agent(
        role="Tech Analyst",
        goal="Compare A2A communication patterns on coupling, scalability, and complexity",
        backstory=(
            "You have 15 years of experience in enterprise architecture.  "
            "You love building comparison matrices and always quantify trade-offs "
            "rather than making vague qualitative statements."
        ),
        verbose=True,
        allow_delegation=False,
        llm="gpt-4o-mini",
    )

    writer = Agent(
        role="Technical Writer",
        goal="Create a clear executive summary of A2A patterns for engineering leadership",
        backstory=(
            "You specialise in translating complex technical topics into "
            "decision-maker-friendly documents.  Your writing is concise, "
            "structured, and always ends with a concrete recommendation."
        ),
        verbose=True,
        allow_delegation=False,
        llm="gpt-4o-mini",
    )

    # Patch execute_task BEFORE the agents are handed to the crew
    researcher.execute_task = _make_mock_execute("researcher", "research")  # type: ignore
    analyst.execute_task    = _make_mock_execute("analyst",    "compar")    # type: ignore
    writer.execute_task     = _make_mock_execute("writer",     "summary")   # type: ignore

    # ── Tasks ───────────────────────────────────────────────────────────────
    # Each task has a description and an expected_output (used by CrewAI to
    # validate and format the agent's response).

    task_research = Task(
        description=(
            "Research the 3 most important agent-to-agent (A2A) communication patterns. "
            "For each pattern, document: (1) how it works, (2) typical use cases, "
            "(3) key trade-offs."
        ),
        expected_output=(
            "A structured report with 3 sections, one per pattern, each covering "
            "mechanism, use cases, and trade-offs."
        ),
        agent=researcher,
    )

    task_analysis = Task(
        description=(
            "Compare the 3 A2A patterns identified by the researcher on the following "
            "dimensions: coupling, scalability, complexity, fault tolerance, observability. "
            "Produce a comparison table and a recommendation matrix."
        ),
        expected_output=(
            "A markdown table comparing the patterns plus a recommendation matrix "
            "mapping use-case profiles to the best pattern."
        ),
        agent=analyst,
        context=[task_research],  # receives researcher's output as context
    )

    task_writing = Task(
        description=(
            "Write an executive summary of the A2A pattern research and analysis. "
            "Audience: engineering leadership.  Length: 200-400 words. "
            "End with a concrete recommendation."
        ),
        expected_output=(
            "An executive summary in plain prose (no bullet overload) with a "
            "clear final recommendation paragraph."
        ),
        agent=writer,
        context=[task_research, task_analysis],
    )

    # ── Crew ────────────────────────────────────────────────────────────────
    crew = Crew(
        agents=[researcher, analyst, writer],
        tasks=[task_research, task_analysis, task_writing],
        process=Process.sequential,  # tasks run in order, outputs chain forward
        verbose=True,
    )

    return crew
