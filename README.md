# A2A Walkthrough — Agent Interoperability Monorepo

A hands-on learning resource for AI engineers who want to deeply understand
**agent-to-agent communication patterns**, standards, and frameworks.

## What's Inside

| # | Pattern / Technology | Description |
|---|---|---|
| 01 | [Direct Request-Response](01-direct-request-response/) | Simplest agent communication via HTTP |
| 02 | [Hierarchical Delegation](02-hierarchical-delegation/) | Orchestrator decomposes tasks for specialist workers |
| 03 | [Publish-Subscribe](03-publish-subscribe/) | Loose coupling via Redis pub/sub channels |
| 04 | [Blackboard](04-blackboard/) | Shared state workspace for collaborative agents |
| 05 | [Google A2A Protocol](05-a2a-protocol/) | Cross-vendor agent interoperability standard |
| 06 | [Anthropic MCP](06-mcp/) | Standard interface for LLM tool/data access |
| 07 | [OpenAI Agents SDK](07-openai-agents-sdk/) | Handoff-based agent routing |
| 08 | [LangGraph](08-langgraph/) | State-machine multi-agent workflows |
| 09 | [CrewAI](09-crewai/) | Role-based agent crews |
| 10 | [AutoGen](10-autogen/) | Conversational multi-agent group chat |

## Learning Guide

Start with [`docs/LEARNING_GUIDE.md`](docs/LEARNING_GUIDE.md) for a lecture-style
deep dive into each pattern — theory, trade-offs, and how they relate to each other.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- (Optional) OpenAI/Anthropic API key for patterns 7-10

### Start Shared Infrastructure
```bash
docker compose up -d
```

This starts:
- **Redis** on `localhost:6379` — used by patterns 03 and 04
- **Postgres** on `localhost:5432` — used by pattern 04 (persistent blackboard)

### Run Any Implementation
```bash
cd 01-direct-request-response
pip install -r requirements.txt
python agent_b.py &       # start the server
python agent_a.py         # run the client
pytest test_integration.py
```

See the README in each directory for specific instructions.

## Implementation Plan

See [`docs/PLAN.md`](docs/PLAN.md) for the full milestone plan and task tracking.

## Research

- [`docs/requirements.md`](docs/requirements.md) — Original project requirements
- [`docs/shallow_research.md`](docs/shallow_research.md) — Pattern overview
- [`docs/Agent to Agent Research Report.md`](<docs/Agent to Agent Research Report.md>) — Deep research report
