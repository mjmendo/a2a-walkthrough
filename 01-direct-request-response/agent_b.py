"""
Agent B — FastAPI server that exposes POST /task.

Transformation: reverses the input string and uppercases it.
This is the simplest possible "agent": it receives a request and
returns a deterministic response with zero external dependencies.
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Agent B", description="Direct request-response worker agent")


class TaskRequest(BaseModel):
    """Incoming task payload."""
    input: str


class TaskResponse(BaseModel):
    """Outgoing task result."""
    result: str
    agent: str = "agent_b"


@app.post("/task", response_model=TaskResponse)
def handle_task(request: TaskRequest) -> TaskResponse:
    """
    Receive a task, process it, and return a result synchronously.

    Transformation applied: reverse the string, then uppercase.
    Example: "hello" -> "OLLEH"
    """
    reversed_upper = request.input[::-1].upper()
    print(f"[agent_b] Received: {request.input!r}  ->  Result: {reversed_upper!r}")
    return TaskResponse(result=reversed_upper)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
