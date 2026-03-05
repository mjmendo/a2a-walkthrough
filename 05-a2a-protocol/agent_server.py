"""
A2A-compliant FastAPI server.

Implements all three surfaces required by the spec:
  1. GET  /.well-known/agent.json  — Agent Card discovery
  2. POST /rpc                     — JSON-RPC 2.0 task execution (tasks/send)
  3. GET  /rpc/stream/{taskId}     — SSE streaming for long-running tasks

Design note: we keep task state in a plain in-memory dict so the server
has zero external dependencies.  A production agent would use Redis or a DB.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from agent_card import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Message,
    Part,
    Task,
    TaskStatus,
    TextPart,
)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="A2A Echo Agent",
    description="Minimal spec-correct Google A2A implementation",
    version="1.0.0",
)

# In-memory task store  {taskId: Task}
_tasks: dict[str, Task] = {}

# ANSI colours for server-side logs
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Agent Card — static discovery document
# ---------------------------------------------------------------------------

AGENT_CARD = AgentCard(
    name="Echo Agent",
    description="Reverses and uppercases any text input — a minimal A2A demo.",
    url="http://localhost:8005/rpc",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(
            id="echo_reverse",
            name="Echo Reverse",
            description="Returns the input text reversed and uppercased.",
        ),
        AgentSkill(
            id="echo_label",
            name="Echo Label",
            description="Prepends a skill label to the transformed text.",
        ),
    ],
)


@app.get("/.well-known/agent.json", tags=["Discovery"])
def get_agent_card() -> dict[str, Any]:
    """
    Return the Agent Card as JSON.

    Any A2A client should fetch this endpoint first to understand what
    the agent can do and how to call it.
    """
    print(f"{CYAN}[agent_server] GET /.well-known/agent.json{RESET}")
    return AGENT_CARD.model_dump()


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 helpers
# ---------------------------------------------------------------------------


def _jsonrpc_error(id: Any, code: int, message: str) -> dict[str, Any]:
    """Build a spec-compliant JSON-RPC 2.0 error response."""
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def _jsonrpc_result(id: Any, result: Any) -> dict[str, Any]:
    """Build a spec-compliant JSON-RPC 2.0 success response."""
    return {"jsonrpc": "2.0", "id": id, "result": result}


# ---------------------------------------------------------------------------
# Core task processing
# ---------------------------------------------------------------------------


def _process_task(task: Task) -> Task:
    """
    Apply the agent's skill: reverse + uppercase each text part.

    A real agent would invoke an LLM or sub-process here.
    We keep it deterministic so the demo is easy to reason about.
    """
    input_text = task.input.text
    transformed = input_text[::-1].upper()
    label = f"[echo_reverse] {transformed}"

    task.status = TaskStatus.COMPLETED
    task.output = Message(
        role="agent",
        parts=[TextPart(content=label)],
    )
    print(f"{GREEN}[agent_server] Task {task.id!r}: {input_text!r} → {label!r}{RESET}")
    return task


# ---------------------------------------------------------------------------
# POST /rpc — JSON-RPC 2.0 endpoint
# ---------------------------------------------------------------------------


@app.post("/rpc", tags=["RPC"])
async def handle_rpc(body: dict[str, Any]) -> JSONResponse:
    """
    JSON-RPC 2.0 dispatcher.

    Currently handles the single method ``tasks/send``.
    Unknown methods return a ``-32601 Method not found`` error per spec.

    Request shape:
        {
          "jsonrpc": "2.0",
          "id": "...",
          "method": "tasks/send",
          "params": {
            "taskId": "...",
            "message": { "role": "user", "parts": [{"type": "text", "content": "..."}] }
          }
        }
    """
    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    print(f"{YELLOW}[agent_server] POST /rpc  method={method!r}  id={req_id!r}{RESET}")

    if method != "tasks/send":
        return JSONResponse(
            _jsonrpc_error(req_id, -32601, f"Method not found: {method!r}")
        )

    # Validate required params
    task_id = params.get("taskId") or str(uuid.uuid4())
    raw_message = params.get("message")
    if raw_message is None:
        return JSONResponse(_jsonrpc_error(req_id, -32602, "params.message is required"))

    try:
        message = Message.model_validate(raw_message)
    except Exception as exc:
        return JSONResponse(_jsonrpc_error(req_id, -32602, f"Invalid message: {exc}"))

    # Create, store, and process the task synchronously
    task = Task(id=task_id, input=message)
    _tasks[task_id] = task
    completed_task = _process_task(task)
    _tasks[task_id] = completed_task

    return JSONResponse(
        _jsonrpc_result(req_id, completed_task.model_dump())
    )


# ---------------------------------------------------------------------------
# GET /rpc/stream/{taskId} — SSE streaming endpoint
# ---------------------------------------------------------------------------


@app.get("/rpc/stream/{task_id}", tags=["Streaming"])
async def stream_task(task_id: str) -> EventSourceResponse:
    """
    Server-Sent Events stream for a task.

    Yields:
      - 3 × ``working`` events (simulating incremental progress)
      - 1 × ``completed`` event with the final output

    A client subscribes here after calling ``tasks/send`` to watch progress.
    SSE lets us push updates without the client polling.
    """
    print(f"{MAGENTA}[agent_server] SSE stream opened for task {task_id!r}{RESET}")

    async def event_generator():
        # Simulate 3 working pulses (100 ms apart)
        for step in range(1, 4):
            await asyncio.sleep(0.1)
            payload = json.dumps(
                {"taskId": task_id, "status": "working", "step": step}
            )
            print(f"{MAGENTA}[agent_server] SSE working step {step}/3{RESET}")
            yield {"event": "task_update", "data": payload}

        # Emit completed event
        task = _tasks.get(task_id)
        if task is None:
            # Task unknown — create a stub so the stream still terminates cleanly
            payload = json.dumps(
                {"taskId": task_id, "status": "failed", "error": "task not found"}
            )
            yield {"event": "task_update", "data": payload}
        else:
            payload = json.dumps(task.model_dump())
            print(f"{MAGENTA}[agent_server] SSE completed for task {task_id!r}{RESET}")
            yield {"event": "task_update", "data": payload}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    print(f"{CYAN}Starting A2A Echo Agent on http://localhost:8005{RESET}")
    uvicorn.run(app, host="0.0.0.0", port=8005, log_level="info")
