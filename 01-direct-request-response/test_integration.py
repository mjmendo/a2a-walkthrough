"""
Integration tests for Pattern 1: Direct Request-Response.

Uses FastAPI's TestClient so Agent B runs in-process — no network needed.
"""

import pytest
from fastapi.testclient import TestClient

from agent_b import app

client = TestClient(app)


def test_basic_reverse_and_uppercase():
    """The core transformation: reverse + uppercase."""
    response = client.post("/task", json={"input": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "OLLEH"
    assert body["agent"] == "agent_b"


def test_empty_string():
    """Reversing an empty string should return an empty string."""
    response = client.post("/task", json={"input": ""})
    assert response.status_code == 200
    assert response.json()["result"] == ""


def test_single_character():
    response = client.post("/task", json={"input": "x"})
    assert response.status_code == 200
    assert response.json()["result"] == "X"


def test_already_uppercase():
    """Already-uppercase input reversed stays uppercase."""
    response = client.post("/task", json={"input": "ABC"})
    assert response.status_code == 200
    assert response.json()["result"] == "CBA"


def test_multiword_input():
    response = client.post("/task", json={"input": "agent to agent"})
    assert response.status_code == 200
    assert response.json()["result"] == "TNEGA OT TNEGA"


def test_missing_input_field_returns_422():
    """Pydantic validation rejects requests without the required 'input' field."""
    response = client.post("/task", json={})
    assert response.status_code == 422


def test_agent_field_always_agent_b():
    """The 'agent' field identifies the responder."""
    response = client.post("/task", json={"input": "test"})
    assert response.json()["agent"] == "agent_b"
