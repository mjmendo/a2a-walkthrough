# A2A Walkthrough — Implementation Plan

> Last updated: 2026-03-05

## Goal

Build a self-contained monorepo that demonstrates every major pattern of
agent-to-agent interoperability, with runnable code and a learning guide,
aimed at an AI engineer wanting to become an expert in this space.

---

## Scope of Patterns

| # | Pattern | Directory | Complexity | Status |
|---|---------|-----------|-----------|--------|
| 1 | Direct Request-Response | `01-direct-request-response/` | Low | TODO |
| 2 | Hierarchical Delegation (Orchestrator-Worker) | `02-hierarchical-delegation/` | Medium | TODO |
| 3 | Publish-Subscribe | `03-publish-subscribe/` | Medium | TODO |
| 4 | Blackboard | `04-blackboard/` | Medium | TODO |
| 5 | Google A2A Protocol | `05-a2a-protocol/` | High | TODO |
| 6 | Anthropic MCP (Tool/Data Interop) | `06-mcp/` | High | TODO |
| 7 | OpenAI Agents SDK (Handoffs) | `07-openai-agents-sdk/` | Medium | TODO |
| 8 | LangGraph (State-Machine Multi-Agent) | `08-langgraph/` | High | TODO |
| 9 | CrewAI (Role-Based Crews) | `09-crewai/` | Medium | TODO |
| 10 | AutoGen / Microsoft Agent Framework | `10-autogen/` | Medium | TODO |
| 11 | OpenClaw Announcement (Subagent Coordination) | `11-openclaw-announcement/` | High | Done |

---

## Milestones

### M0 — Foundation (Day 1)
- [x] Initialize git repository
- [x] Commit existing research docs
- [ ] Create `docker-compose.yml` with shared infrastructure (Redis, Postgres)
- [ ] Create learning guide outline (`docs/LEARNING_GUIDE.md`)
- [ ] Scaffold each implementation directory with README

### M1 — Fundamental Patterns (Days 2-3)
Implement patterns 1-4 (no AI framework dependencies, pure communication patterns):
- [ ] **01** Direct Request-Response: two Python processes talking via HTTP/JSON-RPC
- [ ] **02** Hierarchical Delegation: orchestrator process delegating to typed worker agents
- [ ] **03** Publish-Subscribe: agents communicating via Redis pub/sub channels
- [ ] **04** Blackboard: agents reading/writing a shared Redis/Postgres workspace

### M2 — Interoperability Standards (Days 4-5)
- [ ] **05** Google A2A Protocol: Agent Cards, JSON-RPC 2.0, task lifecycle, streaming
- [ ] **06** Anthropic MCP: MCP server exposing tools, MCP client consuming them

### M3 — Framework Implementations (Days 6-8)
- [ ] **07** OpenAI Agents SDK: triage agent → specialist handoff with traces
- [ ] **08** LangGraph: multi-node state machine with conditional routing
- [ ] **09** CrewAI: three-agent crew with roles, goals, and backstories
- [ ] **10** AutoGen: conversational multi-agent with human-in-the-loop

### M4 — Learning Guide & Polish (Days 9-10)
- [ ] Complete `docs/LEARNING_GUIDE.md` with detailed explanations
- [ ] Add architecture diagrams (Mermaid) to each README
- [ ] Verify all implementations run cleanly with `docker compose up`
- [ ] Final git tag `v1.0`

---

## Shared Infrastructure

All patterns that need external services share a single `docker-compose.yml` at
the repo root, exposing:
- **Redis** on `localhost:6379` — used by Pub-Sub and Blackboard
- **Postgres** on `localhost:5432` — used by Blackboard (persistent workspace)

Individual implementations that need AI model inference depend on environment
variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) set by the user.

---

## Directory Layout

```
a2a-walkthrough/
├── docker-compose.yml          # Shared infra (Redis, Postgres)
├── docs/
│   ├── requirements.md
│   ├── PLAN.md                 # This file
│   ├── LEARNING_GUIDE.md       # Lecture-style narrative
│   ├── shallow_research.md
│   └── Agent to Agent Research Report.md
├── 01-direct-request-response/
│   ├── README.md
│   ├── agent_a.py
│   ├── agent_b.py
│   └── test_integration.py
├── 02-hierarchical-delegation/
│   ├── README.md
│   ├── orchestrator.py
│   ├── worker_research.py
│   ├── worker_summarize.py
│   └── test_integration.py
├── 03-publish-subscribe/
│   ├── README.md
│   ├── publisher_agent.py
│   ├── subscriber_agent.py
│   └── test_integration.py
├── 04-blackboard/
│   ├── README.md
│   ├── blackboard.py
│   ├── agent_analyzer.py
│   ├── agent_writer.py
│   └── test_integration.py
├── 05-a2a-protocol/
│   ├── README.md
│   ├── agent_server.py         # Exposes Agent Card + JSON-RPC task API
│   ├── agent_client.py         # Discovers and calls the agent
│   └── test_integration.py
├── 06-mcp/
│   ├── README.md
│   ├── mcp_server.py           # Exposes tools via MCP protocol
│   ├── mcp_client.py           # Consumes tools via MCP
│   └── test_integration.py
├── 07-openai-agents-sdk/
│   ├── README.md
│   ├── main.py
│   └── test_integration.py
├── 08-langgraph/
│   ├── README.md
│   ├── graph.py
│   └── test_integration.py
├── 09-crewai/
│   ├── README.md
│   ├── crew.py
│   └── test_integration.py
├── 10-autogen/
│   ├── README.md
│   ├── agents.py
│   └── test_integration.py
└── 11-openclaw-announcement/
    ├── README.md
    ├── gateway.py
    ├── subagent.py
    ├── main_agent.py
    └── test_integration.py
```

---

## Task Tracking

| Task | Assignee | Priority | Status |
|------|----------|----------|--------|
| docker-compose.yml | Claude | High | TODO |
| 01-direct-request-response | Claude | High | TODO |
| 02-hierarchical-delegation | Claude | High | TODO |
| 03-publish-subscribe | Claude | High | TODO |
| 04-blackboard | Claude | Medium | TODO |
| 05-a2a-protocol | Claude | Medium | TODO |
| 06-mcp | Claude | Medium | TODO |
| 07-openai-agents-sdk | Claude | Medium | TODO |
| 08-langgraph | Claude | Medium | TODO |
| 09-crewai | Claude | Medium | TODO |
| 10-autogen | Claude | Medium | TODO |
| 11-openclaw-announcement | Claude | High | Done |
| LEARNING_GUIDE.md | Claude | High | TODO |
