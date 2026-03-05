"""
graph.py — Builds, compiles, and runs the LangGraph research pipeline.

LangGraph key concepts shown here:
  - StateGraph: a graph whose nodes share a typed state dict.
  - add_node / add_edge: declarative graph construction.
  - add_conditional_edges: branch on a function of the current state.
  - Cycles: the review → revise → draft loop demonstrates that LangGraph
    supports cycles (unlike simple DAG frameworks).
  - compile(): validates the graph and returns a runnable CompiledGraph.
  - invoke(): run the graph synchronously with an initial state.

Run:
    python graph.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from langgraph.graph import StateGraph, END

from state import ResearchState
from nodes import (
    draft_node,
    finalize_node,
    research_node,
    review_node,
    revise_node,
)

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
CYAN  = "\033[96m"
GREEN = "\033[92m"
BOLD  = "\033[1m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Conditional edge function
# ---------------------------------------------------------------------------

def should_revise(state: ResearchState) -> str:
    """
    Decide the next node after review_node.

    LangGraph conditional edges work by calling a function that returns a
    *string key*.  That key is looked up in a mapping (provided to
    add_conditional_edges) to find the actual next node name.

    Rules:
      - revision_count == 1 (set by review_node on first review) → revise
      - revision_count >= 2 or review approved                   → finalize
    """
    revision_count = state.get("revision_count", 0)

    # review_node increments revision_count when it requests a revision.
    # After the first revision cycle, review_node leaves revision_count
    # unchanged (approval), so we check if revision_count equals exactly 1
    # after the *first* review.  The second review will have revision_count=1
    # but the feedback will say "approved" — we use revision_count < 2 as
    # a simpler proxy: if we have been through exactly one revision, revise;
    # otherwise finalize.
    #
    # A cleaner approach (used in production) is to store a separate
    # "needs_revision: bool" field.  We keep revision_count for simplicity.

    # After first review: revision_count was set to 1 by review_node.
    # After second review: review_node did NOT increment (approved), so
    # revision_count is still 1, but we have already gone through revise once.
    # We track "revise iterations" by comparing with a threshold.
    if revision_count < 2:
        # Check if this is the first review (revision_count became 1 just now)
        # versus a subsequent review. Because review_node only sets count to 1
        # on the FIRST review (and leaves it at 1 on approval), we use a
        # simple heuristic: if revision_count == 1 AND draft doesn't contain
        # "Revision Notes", we haven't revised yet.
        draft = state.get("draft", "")
        if revision_count == 1 and "Revision Notes" not in draft:
            return "revise"

    return "finalize"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> "CompiledGraph":
    """
    Construct and compile the research pipeline graph.

    Graph topology:
        START → research → draft → review → [conditional]
                                              ├── revise → draft (loop)
                                              └── finalize → END
    """
    graph = StateGraph(ResearchState)

    # ── Register nodes ────────────────────────────────────────────────────
    graph.add_node("research", research_node)
    graph.add_node("draft",    draft_node)
    graph.add_node("review",   review_node)
    graph.add_node("revise",   revise_node)
    graph.add_node("finalize", finalize_node)

    # ── Entry point ────────────────────────────────────────────────────────
    graph.set_entry_point("research")

    # ── Linear edges ──────────────────────────────────────────────────────
    graph.add_edge("research", "draft")
    graph.add_edge("draft",    "review")

    # ── Conditional edge (the interesting bit) ────────────────────────────
    # After review, either loop back through revise→draft, or go to finalize.
    graph.add_conditional_edges(
        "review",           # source node
        should_revise,      # function(state) → str key
        {
            "revise":   "revise",    # key "revise"   → node "revise"
            "finalize": "finalize",  # key "finalize" → node "finalize"
        },
    )

    # ── Cycle: revise loops back to draft ────────────────────────────────
    graph.add_edge("revise", "draft")

    # ── Terminal edge ─────────────────────────────────────────────────────
    graph.add_edge("finalize", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the graph and pretty-print each state transition."""
    print(f"\n{BOLD}{CYAN}=== LangGraph Research Pipeline Demo ==={RESET}")
    print(f"{CYAN}Building graph ...{RESET}")

    app = build_graph()

    initial_state: ResearchState = {
        "topic": "agent communication patterns",
        "research": [],
        "draft": "",
        "feedback": "",
        "revision_count": 0,
        "final": "",
    }

    print(f"{CYAN}Initial state:{RESET} topic={initial_state['topic']!r}")
    print(f"{CYAN}Running graph ...{RESET}")

    # invoke() runs the graph synchronously and returns the final state.
    final_state = app.invoke(initial_state)

    print(f"\n{BOLD}{CYAN}=== Graph Execution Complete ==={RESET}")
    print(f"{GREEN}Revision cycles:{RESET} {final_state.get('revision_count', 0)}")
    print(f"{GREEN}Findings collected:{RESET} {len(final_state.get('research', []))}")
    print(f"\n{GREEN}Final document (first 500 chars):{RESET}")
    print(final_state.get("final", "")[:500])
    print(f"\n{BOLD}{CYAN}=== Done ==={RESET}\n")


if __name__ == "__main__":
    main()
