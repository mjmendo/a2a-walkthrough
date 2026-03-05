"""
Integration tests for Pattern 5: Google A2A Protocol.

All tests run in-process using FastAPI's TestClient — no live server needed.
The TestClient wraps the ASGI app in a synchronous requests-compatible interface,
so we can exercise the full HTTP layer without network overhead.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from agent_server import AGENT_CARD, app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Agent Card discovery
# ---------------------------------------------------------------------------


class TestAgentCardEndpoint:
    """GET /.well-known/agent.json"""

    def test_status_200(self):
        resp = client.get("/.well-known/agent.json")
        assert resp.status_code == 200

    def test_returns_json(self):
        resp = client.get("/.well-known/agent.json")
        card = resp.json()
        assert isinstance(card, dict)

    def test_required_fields_present(self):
        card = client.get("/.well-known/agent.json").json()
        for field in ("name", "description", "url", "version", "capabilities", "skills"):
            assert field in card, f"Missing field: {field!r}"

    def test_streaming_capability_true(self):
        card = client.get("/.well-known/agent.json").json()
        assert card["capabilities"]["streaming"] is True

    def test_skills_non_empty(self):
        card = client.get("/.well-known/agent.json").json()
        assert len(card["skills"]) >= 1

    def test_skill_has_required_fields(self):
        card = client.get("/.well-known/agent.json").json()
        for skill in card["skills"]:
            assert "id" in skill
            assert "name" in skill
            assert "description" in skill


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 — tasks/send
# ---------------------------------------------------------------------------


class TestTasksSendMethod:
    """POST /rpc — tasks/send"""

    def _rpc(self, text: str, task_id: str = "test-task-1") -> dict:
        """Helper: send a tasks/send RPC call."""
        payload = {
            "jsonrpc": "2.0",
            "id": task_id,
            "method": "tasks/send",
            "params": {
                "taskId": task_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "content": text}],
                },
            },
        }
        resp = client.post("/rpc", json=payload)
        assert resp.status_code == 200
        return resp.json()

    def test_jsonrpc_envelope_shape(self):
        body = self._rpc("hello")
        assert body["jsonrpc"] == "2.0"
        assert "result" in body
        assert "error" not in body

    def test_task_status_completed(self):
        body = self._rpc("hello")
        assert body["result"]["status"] == "completed"

    def test_output_is_reversed_uppercased(self):
        body = self._rpc("hello")
        parts = body["result"]["output"]["parts"]
        text = " ".join(p["content"] for p in parts)
        # "hello" reversed → "olleh", uppercase → "OLLEH", labelled
        assert "OLLEH" in text

    def test_empty_string_does_not_crash(self):
        body = self._rpc("")
        assert body["result"]["status"] == "completed"

    def test_unknown_method_returns_error(self):
        resp = client.post(
            "/rpc",
            json={"jsonrpc": "2.0", "id": "x", "method": "tasks/unknown", "params": {}},
        )
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32601

    def test_missing_message_returns_error(self):
        resp = client.post(
            "/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "y",
                "method": "tasks/send",
                "params": {"taskId": "t1"},  # message omitted
            },
        )
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32602

    def test_output_role_is_agent(self):
        body = self._rpc("test input")
        assert body["result"]["output"]["role"] == "agent"

    def test_task_id_preserved(self):
        body = self._rpc("anything", task_id="my-custom-id")
        assert body["result"]["id"] == "my-custom-id"


# ---------------------------------------------------------------------------
# SSE streaming endpoint
# ---------------------------------------------------------------------------


class TestSSEStream:
    """GET /rpc/stream/{taskId}"""

    def _send_and_stream(self, text: str = "streaming test") -> list[dict]:
        """Send a task then collect all SSE events from the stream."""
        # First register the task so the server knows it
        task_id = "stream-test-1"
        client.post(
            "/rpc",
            json={
                "jsonrpc": "2.0",
                "id": task_id,
                "method": "tasks/send",
                "params": {
                    "taskId": task_id,
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "content": text}],
                    },
                },
            },
        )

        # Collect SSE events
        events: list[dict] = []
        with client.stream("GET", f"/rpc/stream/{task_id}") as resp:
            assert resp.status_code == 200
            for line in resp.iter_lines():
                line = line.strip()
                if line.startswith("data:"):
                    data_str = line[len("data:"):].strip()
                    try:
                        events.append(json.loads(data_str))
                    except json.JSONDecodeError:
                        pass
        return events

    def test_stream_returns_200(self):
        task_id = "stream-200-test"
        client.post(
            "/rpc",
            json={
                "jsonrpc": "2.0",
                "id": task_id,
                "method": "tasks/send",
                "params": {
                    "taskId": task_id,
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "content": "ping"}],
                    },
                },
            },
        )
        resp = client.get(f"/rpc/stream/{task_id}")
        assert resp.status_code == 200

    def test_stream_emits_working_events(self):
        events = self._send_and_stream()
        working = [e for e in events if e.get("status") == "working"]
        assert len(working) == 3

    def test_stream_final_event_is_completed(self):
        events = self._send_and_stream()
        assert events[-1].get("status") == "completed"

    def test_stream_working_steps_are_sequential(self):
        events = self._send_and_stream()
        working = [e for e in events if e.get("status") == "working"]
        steps = [e.get("step") for e in working]
        assert steps == [1, 2, 3]

    def test_unknown_task_stream_returns_failed_event(self):
        events: list[dict] = []
        with client.stream("GET", "/rpc/stream/no-such-task") as resp:
            for line in resp.iter_lines():
                line = line.strip()
                if line.startswith("data:"):
                    try:
                        events.append(json.loads(line[len("data:"):].strip()))
                    except json.JSONDecodeError:
                        pass
        # Working events emitted first, then a failed event at the end
        assert events[-1].get("status") == "failed"
