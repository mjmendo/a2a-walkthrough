There are five well-established communication patterns used in multi-agent AI systems, each suited to different coordination needs.

## Direct Request-Response

The simplest pattern — Agent A calls Agent B directly, waits for a result, and continues. It mirrors standard HTTP/RPC service calls, is easy to trace, and has low latency. The downside is **tight coupling**: A must know B's address and interface, which makes scaling or swapping agents harder. [particula](https://particula.tech/blog/ai-agent-communication-patterns-multi-agent)

## Publish-Subscribe (Pub-Sub)

Agents publish events to named channels (topics); other agents subscribe to the channels they care about. Neither side knows about the other — a new agent can join by simply subscribing without modifying existing agents. This is ideal for pipeline-style workflows and fan-out scenarios, but debugging is harder because you need correlation IDs to trace a request across scattered logs, and message ordering isn't guaranteed by default. [architectureandgovernance](https://www.architectureandgovernance.com/uncategorized/multi-agent-communication-protocols-in-generative-ai-and-agentic-ai-mcp-and-a2a-protocols/)

## Blackboard

Agents collaborate through a **shared workspace** rather than messaging each other directly. Each agent monitors the blackboard for conditions that match its specialty, contributes its output, and steps back — the state evolves until the task is done. This is natural for iterative refinement tasks like multi-pass code review (security agent, style agent, and correctness agent all read the same codebase and write independent findings). The main risks are concurrency conflicts when two agents write simultaneously, and unclear termination conditions. [tetrate](https://tetrate.io/learn/ai/multi-agent-systems)

## Hierarchical Delegation (Orchestrator-Worker)

A supervisor/orchestrator decomposes a task into subtasks and assigns them to specialist workers, who report results back up the chain. OpenClaw's announce system is a variant of this. It maps well to how complex real-world projects are managed, but the orchestrator becomes a single point of failure if not designed carefully. [nexastack](https://www.nexastack.ai/blog/multi-agent-ai-infrastructure)

## Pattern Comparison

| Pattern | Coupling | Best For | Key Risk |
|---|---|---|---|
| Request-Response | Tight | Simple handoffs, low latency | Doesn't scale to many agents |
| Pub-Sub | Loose | Pipelines, fan-out, async | Hard to debug, eventual consistency |
| Blackboard | Shared state | Iterative refinement, multi-expert review | Concurrency conflicts, termination |
| Hierarchical Delegation | Structured | Task decomposition, specialist teams | Single point of failure at top |

## In Practice

Most production systems **combine patterns** rather than picking one. A common hybrid: a top-level orchestrator uses hierarchical delegation, subteams communicate internally via pub-sub, and shared artifacts (documents, code, plans) live on a blackboard. The key is matching each pattern to the specific coordination problem — pub-sub when agents should be independent, blackboard when agents need to *see and build on* each other's contributions, and delegation when the problem naturally decomposes into nested subtasks. [bix-tech](https://bix-tech.com/agent-orchestration-and-agenttoagent-communication-with-langgraph-a-practical-guide/)