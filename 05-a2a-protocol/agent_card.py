"""
Pydantic models for the Google A2A (Agent-to-Agent) protocol.

The A2A spec defines a canonical shape for:
  - AgentCard  : static capability document served at /.well-known/agent.json
  - Task       : the unit of work exchanged between agents
  - Message    : typed payload carrying Parts (text, data, file, …)
  - Part       : the leaf content node (we implement the "text" modality here)

References:
  https://a2a-protocol.org/latest/specification/
  https://github.com/a2aproject/A2A
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agent Card — discovery document
# ---------------------------------------------------------------------------


class AgentSkill(BaseModel):
    """A single skill (capability) that an agent advertises."""

    id: str = Field(..., description="Machine-readable skill identifier")
    name: str = Field(..., description="Human-readable skill name")
    description: str = Field(..., description="What the skill does")


class AgentCapabilities(BaseModel):
    """Feature flags declared by the agent."""

    streaming: bool = Field(
        default=True,
        description="Whether the agent supports SSE streaming for tasks",
    )


class AgentCard(BaseModel):
    """
    Well-known discovery document for a Google A2A-compliant agent.

    A client fetches this from GET /.well-known/agent.json before
    deciding whether (and how) to interact with the agent.
    """

    name: str
    description: str
    url: str = Field(..., description="Base URL of the agent's RPC endpoint")
    version: str = Field(default="1.0.0")
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    skills: list[AgentSkill] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Task lifecycle
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    """Valid states in the A2A task state machine."""

    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Message + Part — the A2A payload model
# ---------------------------------------------------------------------------


class TextPart(BaseModel):
    """A plain-text content part. A2A also defines 'data' and 'file' parts."""

    type: Literal["text"] = "text"
    content: str


# Union alias — extend with DataPart, FilePart when needed
Part = TextPart


class Message(BaseModel):
    """A message exchanged inside a Task, carrying one or more Parts."""

    role: Literal["user", "agent"]
    parts: list[Part] = Field(default_factory=list)

    @property
    def text(self) -> str:
        """Convenience: concatenate all text parts."""
        return " ".join(p.content for p in self.parts if p.type == "text")


class Task(BaseModel):
    """
    The central A2A work unit.

    Lifecycle: submitted → working → completed | failed
    """

    id: str
    status: TaskStatus = TaskStatus.SUBMITTED
    input: Message
    output: Message | None = None
