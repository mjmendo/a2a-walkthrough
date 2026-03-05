# Agent-to-agent Walkthrough

This workspace is a complete monorepo that intends to showcase A2A, sub-agents and agent swarm architectures, implementation and their variations in different implementations, including the trade-offs they represent.

## Excerpt

AI agent interoperability is currently an architecture concern and several approaces exist, implemented in open source projects and frameworks, even though there is a standard proposal by Google (https://github.com/a2aproject/A2A) following a spec (https://a2a-protocol.org/latest/specification/).

Products such as Openclaw, CrewAI, Langchain and many, many others (deep agents mostly) implement substantially different approaches, in an opinionated way, although using well-known patterns (as listed in ./docs/shallow_research.md) such as:

- hierarchical delegation
- publish / subscribe
- direct request-response
- blackboard

## Requirements

- Research deeply and thoroughly in internet the top 10 ai agent frameworks or products, specially opensource, that support agent communication and interoperatbility:
    - find standards, implementations, flavours approaches that are used by the AI engineers and their maturity and trade-offs.
    - classify them as an software architecture research, and generate a catalog with detailed explanations and source code if available.
    - if you need to clone github repositories to have the code at hand, use the ./external-code folder. I created it for that purpose and you have full controll on it.
    - there exists a pretty recent research made by an ai agent in ./docs/Agent to Agent Research Report.md that you can use to guide your research, but do not base it completely on it. You must corroborate, challenge and determine it's relevance and influence in the current ai agent state-of-the-art interoperability.
- Generate an test/showcase implementation of each approach/technique for the user to be able to read the code and execute it to see the guts of each functionality.
    - each approach/technique should be a folder/module in this workspace
    - it is ok if they are implemented in different programming languages, as long as they are self-contained and executable.
    - if they have dependencies on infrastructure, such as a message broker, try to reuse it through a docker container all the implementations can depend on.
    - make just enough unit/integration tests to prove the code is working and help the learning: this wont be productive code.
- Think about a detailed plan with milestones and add a section for task tracking.
    - make the implementation incremental, aiming to showcase the different approaches.
- Generate also a learning guide explaining the different approaches, how they compare, architectural trade-offs, further reading sources. 
    - Imagine a lecture where the user, which is an AI engineer, wants to get a deep dive on the software architecture and implementation aspects of the examples researched and implemented in this project.
- Prioritize the learning curve of the user.


## Constraints

- This workspace must be versioned as a private git repository of mjmendo.
- Every significant change must be versioned immediatly to have a rollback point.
- The generated Plan must be created as a sibling of this document.

## Goal

1. User is on the path to become an expert in A2A, sub-agents and agent swarm interoperability and communication. The goal is not being an expert on a specific framework or approach, but the learning of their existance, differences and trade-offs.
2. Decompose and design one implementation example per significant variation in the spectrum of agent interoperability.
3. It must run in this computer, as a learning-grade, not productive grade. This wont be used in production, likely, ever.
