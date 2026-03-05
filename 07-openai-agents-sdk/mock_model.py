"""
mock_model.py — Scripted response engine for the OpenAI Agents SDK handoff demo.

Because this walkthrough runs offline (no API key needed), we intercept model
calls and return pre-written strings.  The logic is intentionally simple:
scan the incoming message for trigger keywords and pick the matching script.

The OpenAI Agents SDK (formerly Swarm) expects the model to return either:
  - A plain text reply, or
  - A special "handoff" token that routes control to another agent.

We reproduce that contract here without touching any real endpoint.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Keyword → scripted response table
# ---------------------------------------------------------------------------
# Each entry is:  (list_of_keywords, response_text)
# The triage agent uses handoff markers: "HANDOFF:billing_agent" / "HANDOFF:tech_agent"
# Specialist agents return a plain answer.

TRIAGE_SCRIPTS: list[tuple[list[str], str]] = [
    (
        ["bill", "invoice", "charge", "payment", "subscription", "refund", "price"],
        "HANDOFF:billing_agent",
    ),
    (
        ["error", "bug", "crash", "install", "config", "api", "code", "technical", "debug", "setup"],
        "HANDOFF:tech_agent",
    ),
]

BILLING_SCRIPTS: list[tuple[list[str], str]] = [
    (
        ["refund"],
        "Billing Agent: I can process your refund request. Refunds typically appear within 5-7 business days. "
        "Please share your order ID and I will initiate the process.",
    ),
    (
        ["invoice"],
        "Billing Agent: Your latest invoice has been sent to the email on file. "
        "If you need a PDF copy or a different billing period, just let me know.",
    ),
    (
        ["subscription"],
        "Billing Agent: I can see your subscription details. Your current plan renews on the 1st of next month. "
        "Would you like to upgrade, downgrade, or cancel?",
    ),
    (
        ["charge", "payment", "price", "bill"],
        "Billing Agent: I have reviewed your account. The charge of $49.99 was applied on March 1st for the "
        "Professional plan. If this looks incorrect, I can open a dispute on your behalf.",
    ),
]

TECH_SCRIPTS: list[tuple[list[str], str]] = [
    (
        ["error", "crash", "bug"],
        "Tech Agent: I see you are experiencing an error. Please share the full stack trace and your "
        "environment details (OS, Python version, SDK version) so I can pinpoint the root cause.",
    ),
    (
        ["install", "setup", "config"],
        "Tech Agent: For installation issues, run `pip install --upgrade openai-agents` and verify that "
        "your OPENAI_API_KEY environment variable is set. Detailed setup docs are at docs.openai.com/agents.",
    ),
    (
        ["api", "code", "debug"],
        "Tech Agent: The most common API integration mistake is forgetting to await async calls. "
        "Make sure you are using `await Runner.run(agent, messages)` inside an async context.",
    ),
    (
        ["technical"],
        "Tech Agent: Got your technical question. The OpenAI Agents SDK uses a thin abstraction on top of "
        "the Chat Completions API — agents are just system-prompted model calls with optional tool schemas.",
    ),
]

FALLBACK_TRIAGE = (
    "I'm not sure which specialist to route you to. Could you clarify whether "
    "your question is about billing/payments or a technical/integration issue?"
)
FALLBACK_BILLING = (
    "Billing Agent: I did not catch the specific billing topic. Could you describe "
    "your issue — e.g. refund, invoice, subscription change, or unexpected charge?"
)
FALLBACK_TECH = (
    "Tech Agent: I did not catch the specific technical topic. Could you share more "
    "details — e.g. error message, what you were trying to do, and your environment?"
)


def _match(text: str, scripts: list[tuple[list[str], str]], fallback: str) -> str:
    """Return the first matching scripted response, or the fallback."""
    lower = text.lower()
    for keywords, response in scripts:
        if any(kw in lower for kw in keywords):
            return response
    return fallback


def get_triage_response(user_message: str) -> str:
    """Simulate the triage agent deciding where to route the user."""
    return _match(user_message, TRIAGE_SCRIPTS, FALLBACK_TRIAGE)


def get_billing_response(user_message: str) -> str:
    """Simulate the billing specialist answering a billing question."""
    return _match(user_message, BILLING_SCRIPTS, FALLBACK_BILLING)


def get_tech_response(user_message: str) -> str:
    """Simulate the tech specialist answering a technical question."""
    return _match(user_message, TECH_SCRIPTS, FALLBACK_TECH)
