"""
nodes.py — Node functions for the LangGraph research pipeline.

Every node function:
  - Accepts the current ResearchState dict as its only argument.
  - Returns a *partial* dict with only the keys it modified.
  - Must be a pure function (no side effects on state; LangGraph handles merging).

All LLM calls are mocked — the nodes return pre-written strings so the graph
runs offline without any API key.

The graph topology (defined in graph.py):
    research → draft → review ──(needs revision)──► revise → draft (loop)
                                └──(done)──► finalize
"""

from __future__ import annotations

from state import ResearchState

# ---------------------------------------------------------------------------
# ANSI colours for verbose console output
# ---------------------------------------------------------------------------
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
MAGENTA = "\033[95m"
RESET   = "\033[0m"

# ---------------------------------------------------------------------------
# Mock research database
# ---------------------------------------------------------------------------
MOCK_FINDINGS: dict[str, list[str]] = {
    "default": [
        "Finding 1: Direct request-response is the simplest A2A pattern — "
        "tight coupling, low latency, synchronous.",
        "Finding 2: Event-driven patterns decouple agents via a message bus, "
        "enabling fan-out and resilience at the cost of eventual consistency.",
        "Finding 3: Hierarchical delegation introduces an orchestrator that "
        "breaks tasks into subtasks and fans results back up — good for parallelism.",
    ],
    "agent communication": [
        "Finding 1: The A2A protocol (Google, 2024) standardises task exchange "
        "between autonomous agents using JSON-RPC over HTTP.",
        "Finding 2: Shared-memory patterns (blackboard) are efficient for "
        "co-located agents but do not scale across process boundaries.",
        "Finding 3: Capability advertisement (agent cards) lets agents "
        "self-describe so orchestrators can route tasks dynamically.",
    ],
}


def _get_findings(topic: str) -> list[str]:
    """Return topic-relevant mock findings."""
    lower = topic.lower()
    for key, findings in MOCK_FINDINGS.items():
        if key in lower:
            return findings
    return MOCK_FINDINGS["default"]


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def research_node(state: ResearchState) -> dict:
    """
    Mock-research the topic and return 3 findings.

    In a real graph this node would call a search tool, a vector DB, or an LLM
    with retrieval-augmented generation.  Here we return pre-written strings.
    """
    topic = state.get("topic", "unknown topic")
    print(f"\n{CYAN}[research_node]{RESET} Researching: {topic!r}")

    findings = _get_findings(topic)
    for f in findings:
        print(f"  {GREEN}+{RESET} {f}")

    # Return only the keys we modified; LangGraph merges into full state.
    # For lists, LangGraph supports a "reducer" that *appends* rather than
    # replaces.  We configure that reducer in graph.py via add_messages-style
    # annotation.  Here we simply return the full list for clarity.
    return {"research": findings}


def draft_node(state: ResearchState) -> dict:
    """
    Mock-write a draft document based on the research findings.

    Receives: state["research"] (list of findings)
    Returns:  state["draft"]   (a string)
    """
    research = state.get("research", [])
    topic = state.get("topic", "the topic")
    revision = state.get("revision_count", 0)

    print(f"\n{CYAN}[draft_node]{RESET} Writing draft (revision #{revision}) ...")

    bullet_points = "\n".join(f"  - {r}" for r in research)
    draft = (
        f"# {topic.title()}: An Overview\n\n"
        f"## Key Findings\n{bullet_points}\n\n"
        f"## Summary\n"
        f"Agent communication patterns vary significantly in coupling, latency, "
        f"and scalability.  Choosing the right pattern depends on the specific "
        f"requirements of your distributed system.\n"
    )
    if revision > 0:
        draft += (
            f"\n## Revision Notes (revision #{revision})\n"
            f"Incorporated reviewer feedback: added concrete trade-off tables "
            f"and improved section headings for clarity.\n"
        )

    print(f"  {GREEN}Draft written{RESET} ({len(draft)} chars)")
    return {"draft": draft}


def review_node(state: ResearchState) -> dict:
    """
    Mock-review the draft and decide whether another revision is needed.

    Returns:
        feedback:       Review notes (always non-empty).
        revision_count: Incremented if a revision is requested.

    The conditional edge in graph.py reads revision_count to decide whether to
    loop back to revise_node or proceed to finalize_node.
    """
    draft = state.get("draft", "")
    revision_count = state.get("revision_count", 0)

    print(f"\n{CYAN}[review_node]{RESET} Reviewing draft (revision_count={revision_count}) ...")

    if revision_count == 0:
        # First review: request one revision
        feedback = (
            "The draft covers the findings well but lacks concrete trade-off tables. "
            "Please add a comparison table and improve section headings."
        )
        new_count = 1
        print(f"  {YELLOW}Verdict: REVISION NEEDED{RESET}")
    else:
        # Second review: approve
        feedback = (
            "Revision accepted. The trade-off table is clear and the headings are "
            "much improved. Ready for publication."
        )
        new_count = revision_count  # no increment → finalise
        print(f"  {GREEN}Verdict: APPROVED{RESET}")

    print(f"  {MAGENTA}Feedback:{RESET} {feedback}")
    return {"feedback": feedback, "revision_count": new_count}


def revise_node(state: ResearchState) -> dict:
    """
    Mock-revise the draft based on reviewer feedback.

    In a real graph this would call an LLM with the draft + feedback and return
    an improved draft.  Here we simply annotate the existing draft.
    """
    feedback = state.get("feedback", "")
    revision_count = state.get("revision_count", 0)

    print(f"\n{CYAN}[revise_node]{RESET} Revising based on feedback ...")
    print(f"  {MAGENTA}Applying:{RESET} {feedback}")

    # The revision is handled in draft_node on the next iteration (it checks
    # revision_count to add a "Revision Notes" section).  Here we signal that
    # the revision cycle has been recorded.
    print(f"  {GREEN}Revision #{revision_count} queued — returning to draft_node{RESET}")

    # No state change needed here; draft_node will re-draft with the updated
    # revision_count already in state.
    return {}


def finalize_node(state: ResearchState) -> dict:
    """
    Produce the polished final output.

    Sets state["final"] — the presence of this key signals completion.
    """
    draft = state.get("draft", "")
    topic = state.get("topic", "the topic")

    print(f"\n{CYAN}[finalize_node]{RESET} Producing final document ...")

    final = (
        f"=== FINAL DOCUMENT: {topic.upper()} ===\n\n"
        + draft
        + "\n\n[Document approved after peer review. Ready for publication.]\n"
    )

    print(f"  {GREEN}Final document ready{RESET} ({len(final)} chars)")
    return {"final": final}
