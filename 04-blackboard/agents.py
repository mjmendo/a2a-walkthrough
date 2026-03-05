"""
Specialist agents for Pattern 4: Blackboard.

Each agent reads an input key from the blackboard, transforms it, and
writes its output to a new key. Agents do not call each other — they only
interact through the shared Blackboard instance.

Pipeline (sequential in the demo):
  OutlineAgent  reads "topic"   -> writes "outline"
  WriterAgent   reads "outline" -> writes "draft"
  ReviewerAgent reads "draft"   -> writes "review"
"""

import json

from blackboard import Blackboard

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
RESET = "\033[0m"


class OutlineAgent:
    """
    Reads the research topic from the blackboard and produces a section outline.

    Input key:  "topic"
    Output key: "outline"  (JSON list of section name strings)
    """

    def __init__(self, blackboard: Blackboard):
        self.bb = blackboard

    def run(self) -> None:
        """Read topic, generate outline, write to blackboard."""
        topic = self.bb.read("topic")
        if topic is None:
            raise ValueError("OutlineAgent: 'topic' not found on blackboard")

        print(f"{YELLOW}[OutlineAgent]{RESET} Reading topic: {topic!r}")
        self.bb.set_status("outline", "in_progress")

        words = topic.lower().split()
        sections = [
            f"Introduction to {topic}",
            f"Background: {words[0].title()} Fundamentals" if words else "Background",
            f"Core Concepts and Mechanisms",
            f"Real-World Applications of {topic}",
            f"Challenges and Limitations",
            f"Future Directions",
            f"Conclusion",
        ]

        outline_json = json.dumps(sections)
        self.bb.write("outline", outline_json)
        self.bb.set_status("outline", "done")
        print(f"{GREEN}[OutlineAgent]{RESET} Wrote {len(sections)}-section outline to blackboard.")


class WriterAgent:
    """
    Reads the outline from the blackboard and writes a draft for each section.

    Input key:  "outline"
    Output key: "draft"  (string with all sections rendered)
    """

    def __init__(self, blackboard: Blackboard):
        self.bb = blackboard

    def run(self) -> None:
        """Read outline, generate draft section by section, write to blackboard."""
        outline_json = self.bb.read("outline")
        if outline_json is None:
            raise ValueError("WriterAgent: 'outline' not found on blackboard")

        sections: list[str] = json.loads(outline_json)
        print(f"{YELLOW}[WriterAgent]{RESET} Reading outline ({len(sections)} sections).")
        self.bb.set_status("draft", "in_progress")

        draft_parts: list[str] = []
        for section in sections:
            body = (
                f"This section covers {section.lower()}. "
                f"[Placeholder content — {len(section) * 3} words of analysis go here.] "
                f"Key insight: the subject exhibits measurable properties worth investigating."
            )
            draft_parts.append(f"## {section}\n\n{body}")
            print(f"{CYAN}[WriterAgent]{RESET} Drafted section: {section!r}")

        draft = "\n\n".join(draft_parts)
        self.bb.write("draft", draft)
        self.bb.set_status("draft", "done")
        print(f"{GREEN}[WriterAgent]{RESET} Draft complete ({len(draft)} chars) written to blackboard.")


class ReviewerAgent:
    """
    Reads the draft from the blackboard and writes a review with findings.

    Input key:  "draft"
    Output key: "review"  (plain text with approval or issues)
    """

    def __init__(self, blackboard: Blackboard):
        self.bb = blackboard

    def run(self) -> None:
        """Read draft, generate review, write to blackboard."""
        draft = self.bb.read("draft")
        if draft is None:
            raise ValueError("ReviewerAgent: 'draft' not found on blackboard")

        print(f"{YELLOW}[ReviewerAgent]{RESET} Reading draft ({len(draft)} chars).")
        self.bb.set_status("review", "in_progress")

        section_count = draft.count("## ")
        word_count_estimate = len(draft.split())
        issues: list[str] = []

        if word_count_estimate < 50:
            issues.append("Draft is too short — needs more content.")
        if section_count < 3:
            issues.append("Too few sections — consider expanding the outline.")

        if issues:
            verdict = "NEEDS_REVISION"
            issue_text = "\n".join(f"  - {i}" for i in issues)
            review = f"STATUS: {verdict}\nISSUES:\n{issue_text}"
            print(f"{RED}[ReviewerAgent]{RESET} Review: {verdict} — {len(issues)} issue(s) found.")
        else:
            verdict = "APPROVED"
            review = (
                f"STATUS: {verdict}\n"
                f"Sections reviewed: {section_count}\n"
                f"Estimated word count: {word_count_estimate}\n"
                f"All sections present and sufficiently detailed.\n"
                f"Document is ready for publication."
            )
            print(f"{GREEN}[ReviewerAgent]{RESET} Review: {verdict}")

        self.bb.write("review", review)
        self.bb.set_status("review", "done")
        print(f"{GREEN}[ReviewerAgent]{RESET} Review written to blackboard.")
