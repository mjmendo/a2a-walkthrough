"""
Integration tests for Pattern 3: Publish-Subscribe.

Uses fakeredis so no real Redis instance is required.
All tests run the full pub/sub pipeline in-process using threads.
"""

import threading
import time

import fakeredis
import pytest

from agents import PublisherAgent, ResultCollector, SubscriberAgent

TASKS_CHANNEL = "tasks"
RESULTS_CHANNEL = "results"


def make_redis():
    """Create a shared fakeredis server so pub/sub works across clients."""
    server = fakeredis.FakeServer()
    return fakeredis.FakeRedis(server=server, decode_responses=True)


def run_pipeline(tasks: list[str], redis_factory) -> list[dict]:
    """
    Helper: wire up all three agents against a shared Redis instance,
    publish tasks, and return the collected results.
    """
    r = redis_factory()

    publisher = PublisherAgent(r)
    subscriber = SubscriberAgent(r)
    collector = ResultCollector(r)

    count = len(tasks)

    sub_thread = threading.Thread(target=subscriber.start, args=(count,), daemon=True)
    col_thread = threading.Thread(target=collector.collect, args=(count,), daemon=True)

    sub_thread.start()
    col_thread.start()
    time.sleep(0.1)  # let subscriptions establish

    publisher.publish_tasks(tasks)

    sub_thread.join(timeout=10)
    col_thread.join(timeout=10)

    return collector.results


@pytest.fixture
def redis_factory():
    """Return a factory that creates clients sharing one FakeServer."""
    server = fakeredis.FakeServer()

    def factory():
        return fakeredis.FakeRedis(server=server, decode_responses=True)

    return factory


class TestPublisherAgent:
    def test_publish_returns_task_ids(self, redis_factory):
        r = redis_factory()
        publisher = PublisherAgent(r)
        # We can't assert publish count without a subscriber, but ids are returned
        ids = publisher.publish_tasks(["task one", "task two"])
        assert len(ids) == 2
        for tid in ids:
            assert isinstance(tid, str)
            assert len(tid) > 0

    def test_publish_unique_ids(self, redis_factory):
        r = redis_factory()
        publisher = PublisherAgent(r)
        ids = publisher.publish_tasks(["a", "b", "c", "d", "e"])
        assert len(set(ids)) == 5  # all unique


class TestFullPipeline:
    def test_all_results_collected(self, redis_factory):
        tasks = ["alpha", "beta", "gamma"]
        results = run_pipeline(tasks, redis_factory)
        assert len(results) == 3

    def test_results_are_processed(self, redis_factory):
        tasks = ["hello", "world"]
        results = run_pipeline(tasks, redis_factory)
        for res in results:
            assert res["data"].endswith(" [processed]")

    def test_result_schema(self, redis_factory):
        results = run_pipeline(["single task"], redis_factory)
        assert len(results) == 1
        res = results[0]
        assert "event" in res
        assert "data" in res
        assert "id" in res
        assert res["event"] == "task_result"

    def test_five_tasks(self, redis_factory):
        tasks = [f"task-{i}" for i in range(5)]
        results = run_pipeline(tasks, redis_factory)
        assert len(results) == 5

    def test_original_content_preserved(self, redis_factory):
        tasks = ["my important task"]
        results = run_pipeline(tasks, redis_factory)
        assert "my important task" in results[0]["data"]
