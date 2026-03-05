# Agent-to-Agent Interoperability — Deep Dive Learning Guide

> A lecture for AI engineers who want to become experts in the software architecture
> and implementation of multi-agent systems.

---

## Table of Contents

1. [Why This Matters](#1-why-this-matters)
2. [Taxonomy of Agent Interactions](#2-taxonomy-of-agent-interactions)
3. [Pattern 1 — Direct Request-Response](#3-pattern-1--direct-request-response)
4. [Pattern 2 — Hierarchical Delegation](#4-pattern-2--hierarchical-delegation)
5. [Pattern 3 — Publish-Subscribe](#5-pattern-3--publish-subscribe)
6. [Pattern 4 — Blackboard](#6-pattern-4--blackboard)
7. [Standard: Google A2A Protocol](#7-standard-google-a2a-protocol)
8. [Standard: Anthropic MCP](#8-standard-anthropic-mcp)
9. [Framework: OpenAI Agents SDK & Handoffs](#9-framework-openai-agents-sdk--handoffs)
10. [Framework: LangGraph](#10-framework-langgraph)
11. [Framework: CrewAI](#11-framework-crewai)
12. [Framework: AutoGen / Microsoft Agent Framework](#12-framework-autogen--microsoft-agent-framework)
13. [Architecture Trade-offs Comparison](#13-architecture-trade-offs-comparison)
14. [Maturity & Adoption Landscape (2025-2026)](#14-maturity--adoption-landscape-2025-2026)
15. [Further Reading](#15-further-reading)

---

## 1. Why This Matters

In 2024–2026, AI agent systems moved from curiosity to production infrastructure.
Single-agent systems hit a ceiling: one context window, one capability set, one point
of failure. The industry's response has been **multi-agent architectures** — systems
where specialized agents collaborate to handle complex, long-horizon tasks.

The central engineering problem is **coordination**: how do agents communicate,
share state, delegate work, and maintain consistency — without the coordination
overhead overwhelming the value they produce?

This guide explores the answer from first principles (pure communication patterns)
through emerging standards (A2A, MCP) to opinionated frameworks (LangGraph, CrewAI,
AutoGen). Each section gives you:
- The core architectural idea
- Concrete code to run
- Trade-offs that determine when to use it
- How it relates to what came before

---

## 2. Taxonomy of Agent Interactions

Before diving into implementations, let's establish vocabulary:

### By Coupling

| Tight Coupling | Loose Coupling |
|---|---|
| Agent A knows Agent B's address, schema, and timing | Agents only share a protocol or channel |
| Examples: Direct HTTP calls, function calls | Examples: pub/sub topics, blackboard state |
| Easy to trace, hard to scale | Hard to trace, easy to scale |

### By Control Flow

| Centralized | Distributed |
|---|---|
| One orchestrator directs all agents | Agents react to shared events/state |
| Examples: Hierarchical delegation, OpenAI Agents SDK | Examples: Pub/Sub, Blackboard |
| Clearer responsibility, single point of failure | Emergent behavior, harder to reason about |

### By State Management

| Stateless | Stateful |
|---|---|
| Each message is self-contained | Agents maintain context across messages |
| Easy to scale, restart, and replace | Required for multi-turn tasks |
| Examples: HTTP request handlers | Examples: LangGraph nodes with state, Blackboard |

### By Synchrony

| Synchronous | Asynchronous |
|---|---|
| Caller waits for result | Caller continues, result arrives later |
| Simple programming model | Higher throughput, more complexity |
| Examples: Direct Request-Response | Examples: Pub/Sub, A2A streaming |

---

## 3. Pattern 1 — Direct Request-Response

**Code**: `01-direct-request-response/`

### The Pattern

The simplest form of agent communication: Agent A calls Agent B via HTTP (or any
RPC mechanism), waits for a result, and continues.

```
Agent A ──── POST /task ────► Agent B
         ◄── 200 + result ───
```

This mirrors how web services have communicated since the 1990s. In the agent world,
the "input" and "output" are natural language or structured data, but the transport
is identical.

### Why It's Used

- **Simplicity**: every engineer knows HTTP. No new concepts to learn.
- **Traceability**: one request → one response. Easy to log, debug, replay.
- **Latency**: minimal overhead when A and B are co-located or nearby.

### Why It Breaks Down

- **Tight coupling**: Agent A must know B's URL, port, schema, and retry behavior.
- **Availability coupling**: if B is down, A is blocked.
- **Fan-out pain**: if A needs to call 10 agents, it must manage 10 connections.

### When to Use It

- Simple two-agent handoffs with known, stable interfaces
- Low concurrency, synchronous workflows
- Prototyping or when simplicity matters more than scalability

### Connection to Standards

The Google A2A protocol (Pattern 5) is built on HTTP + JSON-RPC 2.0 — it's a
standardized, enriched version of this same pattern with agent discovery and
streaming built in.

---

## 4. Pattern 2 — Hierarchical Delegation

**Code**: `02-hierarchical-delegation/`

### The Pattern

An **orchestrator** decomposes a complex goal into subtasks and assigns them to
specialist **workers**. Workers return results to the orchestrator, which synthesizes
and returns the final answer.

```
                 Orchestrator
                /      |      \
       Worker A    Worker B    Worker C
       (research)  (analyze)  (summarize)
```

This maps directly to how engineering teams work: a tech lead breaks an epic into
stories, assigns them to engineers, reviews PRs, and ships the feature.

### The Decomposition Challenge

Effective orchestration requires the orchestrator to:
1. **Decompose** the goal into independent (or sequenced) subtasks
2. **Route** each subtask to the right specialist
3. **Aggregate** results, handling partial failures
4. **Synthesize** a coherent response

In LLM-based systems, the orchestrator is often the most expensive component — it
makes the planning decisions.

### Trade-offs

**Advantages:**
- Clear responsibility boundaries: each agent is a specialist
- Easy to add new workers without changing the orchestrator interface
- Workers are testable in isolation

**Risks:**
- Orchestrator becomes a **single point of failure**
- Orchestrator becomes a **bottleneck** under load
- Planning quality is bounded by the orchestrator's capability

### Connection to Frameworks

This is the foundational pattern behind OpenAI Agents SDK, CrewAI (hierarchical
process), and LangGraph's "supervisor" pattern. The difference between frameworks
is mainly in *how* the orchestrator makes routing decisions (rule-based vs LLM-driven)
and how errors are handled.

---

## 5. Pattern 3 — Publish-Subscribe

**Code**: `03-publish-subscribe/`

### The Pattern

Agents communicate through **named channels** (topics). Publishers send events
without knowing who's listening. Subscribers receive events without knowing who
sent them. A **message broker** (Redis, Kafka, NATS, etc.) mediates.

```
Publisher ──► [topic: "tasks"] ──► Subscriber A
                                ──► Subscriber B
                                ──► Subscriber C
```

### Why It's Powerful

- **Zero coupling**: publishers and subscribers don't know each other exist
- **Fan-out for free**: one event reaches N subscribers without N API calls
- **Agent lifecycle independence**: subscribers can be added, removed, restarted
  without affecting publishers

### The Debugging Tax

The price of loose coupling is **traceability**. A request in a pub/sub system
becomes an event that triggers more events, which trigger more events. Without
correlation IDs woven through every message, debugging a failure requires reading
logs from 5 services, correlating by timestamp.

Key practices:
- Add `correlation_id` and `trace_id` to every message
- Use structured logging (JSON)
- Invest in distributed tracing (OpenTelemetry)

### Message Ordering

By default, pub/sub systems don't guarantee message ordering. In Kafka, ordering
is per-partition. In Redis pub/sub, messages are delivered in order *within a
connection* but not across reconnections. Design your agents to be **idempotent**
(safe to process the same message twice) and **ordering-tolerant** where possible.

### When to Use It

- Fan-out scenarios: one event needs to trigger many independent agents
- Pipeline workflows: output of one stage becomes input to the next
- When agents must remain independently deployable

---

## 6. Pattern 4 — Blackboard

**Code**: `04-blackboard/`

### The Pattern

Agents collaborate through a **shared workspace** (the blackboard) rather than
messaging each other. Each agent watches for conditions it can act on, writes its
output, and steps back. The task is "done" when the blackboard reaches a terminal
state.

```
         ┌─────────────────────────────┐
         │      BLACKBOARD              │
         │  topic: "agent patterns"    │
         │  outline: [...]             │
         │  draft: "..."               │
         │  review: APPROVED           │
         └─────────────────────────────┘
              ▲         ▲         ▲
        OutlineAgent  Writer  Reviewer
```

### Where It Comes From

The blackboard architecture originated in AI research in the 1970s (HEARSAY speech
recognition system). It's a natural fit for problems where:
- The solution is built incrementally
- Different specialists contribute different parts
- The order of contributions isn't fully predetermined

### Modern Equivalents

In modern AI systems, the "blackboard" takes different forms:
- A **Redis hash** (as in our example)
- A **database table** (persistent, queryable)
- A **shared document** (Google Docs, Notion — used by CrewAI's memory system)
- **LangGraph's State** object (typed, immutable, versioned)

### Concurrency Challenges

When multiple agents can write simultaneously, you get race conditions:
```
Agent A reads draft = "v1"
Agent B reads draft = "v1"
Agent A writes draft = "v2" (added section 1)
Agent B writes draft = "v2" (added section 2, overwrote section 1!)
```

Mitigation:
- **Optimistic locking**: use Redis `WATCH` / transactions
- **Fine-grained keys**: each agent writes to its own key, a merge agent combines
- **Append-only**: agents only append to lists, never overwrite

---

## 7. Standard: Google A2A Protocol

**Code**: `05-a2a-protocol/`

### What Is A2A?

A2A (Agent-to-Agent) is an open protocol proposed by Google (April 2025) and now
governed by the Linux Foundation. It provides a standard interface for agents from
**different vendors and frameworks** to discover each other and exchange tasks.

The key insight: as AI agent ecosystems mature, enterprises will deploy agents built
with different frameworks (one team uses LangGraph, another uses CrewAI, a vendor
uses AutoGen). Without a standard, every cross-framework integration requires
bespoke adapters. A2A is the "HTTP of agent communication."

### Core Concepts

**Agent Card** (discovery):
```json
{
  "name": "Research Agent",
  "description": "Performs web research on given topics",
  "url": "https://agent.example.com",
  "version": "1.0.0",
  "capabilities": { "streaming": true },
  "skills": [
    { "id": "web-research", "name": "Web Research" }
  ]
}
```
Published at `/.well-known/agent.json`. Any client can discover capabilities before
calling.

**Task Lifecycle**:
```
submitted → working → completed
                   ↘ failed
```

**Transport**: JSON-RPC 2.0 over HTTPS. Streaming via Server-Sent Events (SSE).

### How It Differs From Plain HTTP

| Plain HTTP | A2A |
|---|---|
| Custom schema per service | Standardized task/message schema |
| No discovery | Agent Card for discovery |
| No streaming standard | SSE-based streaming built-in |
| One-off integrations | Framework-agnostic interop |

### Maturity (2026)

As of early 2026, A2A is at v0.3+. Google's Vertex AI Agent Builder has preview
support. LangChain/LangGraph has experimental A2A integration. It's the most
promising cross-vendor interop standard, but still maturing.

**Further Reading:**
- Spec: https://a2a-protocol.org/latest/specification/
- GitHub: https://github.com/a2aproject/A2A

---

## 8. Standard: Anthropic MCP

**Code**: `06-mcp/`

### What Is MCP?

MCP (Model Context Protocol), introduced by Anthropic in November 2024, is a
standard interface between **LLM hosts** (AI models, agent runtimes) and **tool/data
providers** (databases, APIs, file systems).

Where A2A is about **agent↔agent** communication, MCP is about **model↔tool**
communication. They're complementary.

```
┌─────────────────────────┐     MCP      ┌─────────────────────┐
│   LLM Host / Agent      │◄────────────►│   MCP Server        │
│   (Claude, ChatGPT, etc)│              │   (tools, resources) │
└─────────────────────────┘              └─────────────────────┘
```

### Core Primitives

- **Tools**: callable functions (like OpenAI function calling, but standardized)
- **Resources**: data the model can read (files, database records, API responses)
- **Prompts**: reusable prompt templates the server exposes

### Transport Options

| Transport | Use Case |
|---|---|
| **stdio** | Local subprocesses; simplest to implement |
| **SSE (HTTP)** | Remote servers; single-direction streaming |
| **Streamable HTTP** | Bidirectional; production-grade |

### Why It Matters

Before MCP, every tool integration was bespoke:
- OpenAI function calling had one schema
- Anthropic tool use had another
- LangChain tools had yet another

MCP creates a vendor-neutral interface. An MCP server built today works with any
MCP-compatible host (Claude, Cursor, Continue, any custom agent runtime).

**Adoption (2026)**: MCP has seen explosive adoption. Hundreds of MCP servers exist
for databases, APIs, file systems, browsers. It's becoming the "USB-C of AI tools."

**Further Reading:**
- https://modelcontextprotocol.io/introduction
- https://github.com/modelcontextprotocol/python-sdk

---

## 9. Framework: OpenAI Agents SDK & Handoffs

**Code**: `07-openai-agents-sdk/`

### The Handoff Model

The OpenAI Agents SDK (evolved from Swarm, March 2025) centers on one key
abstraction: the **handoff**. When an agent decides it can't handle a request, it
hands off control to another agent, passing along the conversation context.

```
User Input ──► Triage Agent ──► [handoff] ──► Billing Agent ──► Response
```

Handoffs are explicit: an agent declares which other agents it can hand off to.
The runtime handles context transfer automatically.

### Agent Model

An agent in this SDK is:
- A **system prompt** defining its persona and capabilities
- A list of **tools** it can call
- A list of **handoffs** (other agents it can delegate to)

```python
billing_agent = Agent(
    name="Billing Agent",
    instructions="You handle billing questions. ...",
    tools=[check_balance, create_refund],
)
triage_agent = Agent(
    name="Triage",
    instructions="Route to the right specialist.",
    handoffs=[billing_agent, tech_agent],
)
```

### Traces

The SDK provides full execution traces: every agent step, tool call, and handoff
is logged, which is critical for debugging multi-agent systems in production.

### vs. LangGraph

| OpenAI Agents SDK | LangGraph |
|---|---|
| Handoffs are implicit (LLM decides) | Routing is explicit (graph edges) |
| Less control, more flexibility | More control, more complexity |
| Best for flat handoff trees | Best for complex graphs with cycles |
| OpenAI-centric | Framework/model-agnostic |

---

## 10. Framework: LangGraph

**Code**: `08-langgraph/`

### The Graph Model

LangGraph (LangChain, GA v1.0 October 2025) models multi-agent workflows as
**directed graphs** where:
- **Nodes** are Python functions (or agents) that read and write state
- **Edges** define the flow between nodes
- **Conditional edges** enable branching and loops
- **State** is a typed dictionary that persists across the entire graph execution

```
research ──► draft ──► review ──► (if revision needed) ──► revise ──► draft
                                └──► (if approved) ──► finalize
```

### Why State Machines for Agents

Complex agent workflows often require:
- **Cycles**: iteration until a condition is met (e.g., "keep revising until approved")
- **Branching**: different paths based on intermediate results
- **Persistence**: survive failures and resume mid-execution

LangGraph provides all three. The state is checkpointed at each node, so if a
long-running workflow fails at step 7, you can resume from step 6 without redoing
everything.

### LangGraph vs. Simple Chains

LangChain chains are **linear** (A → B → C). LangGraph supports **arbitrary graphs**,
including cycles. This is the key capability unlock for agents that need to iterate.

### Production Considerations

- LangGraph has production-grade checkpointing (Postgres, Redis backends)
- LangGraph Cloud provides managed execution and human-in-the-loop review UI
- Full OpenTelemetry tracing via LangSmith

---

## 11. Framework: CrewAI

**Code**: `09-crewai/`

### The Crew Model

CrewAI (OSS v1.0, October 2025) models agents as **crew members** with:
- A **role** (e.g., "Senior Researcher")
- A **goal** (what they're optimizing for)
- A **backstory** (context that shapes their behavior)

Tasks are assigned to agents and executed in sequence (or hierarchically, where
the "manager" agent delegates dynamically).

```python
researcher = Agent(
    role="Senior Researcher",
    goal="Find comprehensive information on agent communication",
    backstory="Expert with 20 years in distributed systems",
)
task = Task(
    description="Research the top 5 A2A patterns",
    agent=researcher,
    expected_output="A structured report with pros/cons",
)
```

### Opinionated vs. Flexible

CrewAI is more opinionated than LangGraph:
- Agents have fixed roles and don't dynamically choose tools (by default)
- Sequential process is the most common and well-tested
- Memory, delegation, and caching are first-class features

This makes CrewAI faster to prototype with but less flexible for unusual workflows.

### When CrewAI Shines

- Content creation pipelines (research → write → review → publish)
- Business process automation with clear role boundaries
- When you want the framework to handle coordination, not you

---

## 12. Framework: AutoGen / Microsoft Agent Framework

**Code**: `10-autogen/`

### The Conversational Model

AutoGen (Microsoft) takes a different approach: agents are **conversational**.
They exchange natural language messages in a **group chat**, and coordination
emerges from the conversation itself.

```
UserProxy: "Research agent communication patterns and write a summary"
    ↓
Planner: "Plan: 1) Research patterns, 2) Write comparative analysis, 3) Format"
    ↓
Executor: "Executing step 1: [research output]"
    ↓
Planner: "Step 1 complete. Proceed with step 2."
    ↓
Executor: "Executing step 2: [analysis output]"
    ↓
Planner: "All steps complete. TERMINATE"
```

### GroupChat

AutoGen's `GroupChat` manages multiple agents, with a `GroupChatManager` that
selects who speaks next (LLM-driven or round-robin). This creates natural
"committee" behavior but can also produce debates or loops.

### Microsoft Agent Framework

Microsoft Agent Framework (announced October 2025) unifies AutoGen and Semantic
Kernel, adding enterprise concerns:
- Approval workflows
- Fine-grained access control
- MCP and A2A integration
- Azure-native deployment

### When AutoGen Shines

- Open-ended tasks where the conversation itself is part of the solution
- Code generation + execution loops (coder agent + executor agent)
- Human-in-the-loop review workflows

---

## 13. Architecture Trade-offs Comparison

| Dimension | Direct RPC | Hierarchical | Pub-Sub | Blackboard | A2A | MCP | Agents SDK | LangGraph | CrewAI | AutoGen |
|---|---|---|---|---|---|---|---|---|---|---|
| **Coupling** | Tight | Medium | Loose | Loose | Medium | Tight (tool) | Medium | Medium | Medium | Loose |
| **Traceability** | Excellent | Good | Poor | Medium | Good | Good | Excellent | Excellent | Good | Medium |
| **Scalability** | Low | Medium | High | Medium | High | N/A | Medium | Medium | Medium | Low |
| **Flexibility** | High | High | High | High | High | Medium | Medium | Very High | Low | High |
| **Complexity** | Low | Medium | Medium | Medium | High | Medium | Low | High | Low | Medium |
| **Iterative Workflows** | No | Partial | No | Yes | Yes | No | Yes | Yes | Partial | Yes |
| **Cross-vendor Interop** | Custom | Custom | Custom | Custom | Yes | Yes | No | Partial | No | No |
| **Production Maturity** | High | High | High | High | Medium | High | High | High | Medium | Medium |

---

## 14. Maturity & Adoption Landscape (2025-2026)

### Standards (Converging)

**MCP** has achieved broad adoption — it's the de facto standard for tool/data
interoperability. Nearly every major AI development tool supports it.

**A2A** is gaining traction but still maturing. v0.3+ in 2025, Linux Foundation
governance signals long-term commitment. Watch for v1.0 in 2026.

### Frameworks (Bifurcating)

The market is splitting into two camps:

**Explicit control** (LangGraph, Microsoft Agent Framework):
- Developers define the graph/workflow
- LLMs fill in the details within each node
- Better for production, auditable workflows
- Steeper learning curve

**Agent autonomy** (CrewAI, AutoGen, OpenAI Agents SDK):
- LLMs make coordination decisions
- Faster to prototype
- Less predictable in production
- Better for creative/open-ended tasks

### What the Industry Is Converging On

1. **Two-layer architecture**: explicit routing at the workflow level, LLM autonomy at
   the task level
2. **Protocol-based interop**: MCP for tools, A2A for agent-to-agent
3. **Observability as first class**: every framework now has built-in tracing
4. **Human-in-the-loop**: approval hooks, not just autonomous execution

---

## 15. Further Reading

### Standards
- A2A Specification: https://a2a-protocol.org/latest/specification/
- A2A GitHub: https://github.com/a2aproject/A2A
- MCP Introduction: https://modelcontextprotocol.io/introduction
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk

### Frameworks
- LangGraph Docs: https://langchain-ai.github.io/langgraph/
- CrewAI Docs: https://docs.crewai.com/
- AutoGen: https://microsoft.github.io/autogen/
- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/

### Research Papers
- "Multi-Agent Collaboration Mechanisms: A Survey of LLMs" (Jan 2025)
- "MultiAgentBench" (ACL 2025) — benchmarking agent coordination
- "Agent Security Bench (ASB)" (ICLR 2025) — agentic security benchmarks
- "MAEBE" (Jun 2025) — emergent multi-agent behavior evaluation

### Architecture References
- https://particula.tech/blog/ai-agent-communication-patterns-multi-agent
- https://www.architectureandgovernance.com/uncategorized/multi-agent-communication-protocols-in-generative-ai-and-agentic-ai-mcp-and-a2a-protocols/
- https://bix-tech.com/agent-orchestration-and-agenttoagent-communication-with-langgraph-a-practical-guide/
