"""
state.py — LangGraph state definition for the research-draft-review pipeline.

LangGraph passes a single *state* dict through every node in the graph.  Each
node receives the current state, does its work, and returns a *partial* update
(only the keys it modified).  LangGraph merges these updates into the shared
state automatically.

Using TypedDict gives us static type checking and makes the schema explicit —
both important for readable, maintainable graphs.

State lifecycle for this demo:
  {}
  → research_node  → {research: [...3 findings...]}
  → draft_node     → {draft: "..."}
  → review_node    → {feedback: "...", revision_count: N}
  → revise_node    → {draft: "...revised..."}   (loops back to draft_node)
  → finalize_node  → {final: "..."}
"""

from __future__ import annotations

from typing import TypedDict


class ResearchState(TypedDict, total=False):
    """
    Shared state flowing through the LangGraph research pipeline.

    Attributes:
        topic:          The research question given by the user.
        research:       Accumulated list of research findings (each node
                        may *append* to this list; LangGraph supports list
                        reducers for exactly this pattern).
        draft:          The current draft document (overwritten on each revision).
        feedback:       Review notes from the review_node.
        revision_count: How many revision cycles have completed so far.
        final:          The polished final document (set only by finalize_node).
    """

    topic: str
    research: list[str]
    draft: str
    feedback: str
    revision_count: int
    final: str
