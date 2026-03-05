"""
Agent classes for Pattern 3: Publish-Subscribe.

Agents communicate through named Redis channels without direct references
to each other. The broker (Redis pub/sub) is the only shared dependency.

Channels:
  "tasks"   - PublisherAgent -> SubscriberAgent
  "results" - SubscriberAgent -> ResultCollector
"""

import json
import threading
import uuid
from typing import Any

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

TASKS_CHANNEL = "tasks"
RESULTS_CHANNEL = "results"


class PublisherAgent:
    """
    Publishes task events to the 'tasks' channel.

    Each event is a JSON-encoded dict:
      {"event": "new_task", "data": str, "id": uuid}

    The publisher has no knowledge of who (if anyone) is listening.
    """

    def __init__(self, redis_client: Any):
        self.redis = redis_client

    def publish_tasks(self, tasks: list[str]) -> list[str]:
        """
        Publish a list of task strings to the tasks channel.

        Args:
            tasks: List of plain-text task descriptions.

        Returns:
            List of task IDs that were published.
        """
        task_ids = []
        for task in tasks:
            task_id = str(uuid.uuid4())[:8]
            message = json.dumps({"event": "new_task", "data": task, "id": task_id})
            self.redis.publish(TASKS_CHANNEL, message)
            task_ids.append(task_id)
            print(f"{YELLOW}[PublisherAgent]{RESET} Published task {task_id!r}: {task!r}")
        return task_ids


class SubscriberAgent:
    """
    Subscribes to the 'tasks' channel, processes each task, and publishes
    the result to the 'results' channel.

    Processing: appends " [processed]" to the task data.
    The subscriber is decoupled from the publisher — it only knows the
    channel names, not who published the tasks.
    """

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._stop = threading.Event()

    def start(self, expected_count: int) -> None:
        """
        Subscribe to 'tasks', process messages, publish to 'results'.

        Args:
            expected_count: Stop after processing this many messages.
        """
        pubsub = self.redis.pubsub()
        pubsub.subscribe(TASKS_CHANNEL)
        processed = 0

        for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            payload = json.loads(raw["data"])
            task_id = payload["id"]
            task_data = payload["data"]
            result_data = task_data + " [processed]"
            print(f"{CYAN}[SubscriberAgent]{RESET} Processing task {task_id!r}: {task_data!r}")
            result_msg = json.dumps({"event": "task_result", "data": result_data, "id": task_id})
            self.redis.publish(RESULTS_CHANNEL, result_msg)
            print(f"{CYAN}[SubscriberAgent]{RESET} Published result for {task_id!r}")
            processed += 1
            if processed >= expected_count:
                break

        pubsub.unsubscribe(TASKS_CHANNEL)


class ResultCollector:
    """
    Subscribes to the 'results' channel and collects all processed results.

    The collector has no knowledge of SubscriberAgent — it only cares
    about the 'results' channel and the message schema.
    """

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self.results: list[dict] = []

    def collect(self, expected_count: int) -> list[dict]:
        """
        Listen on 'results' until expected_count messages are received.

        Args:
            expected_count: Number of result messages to wait for.

        Returns:
            List of result payload dicts.
        """
        pubsub = self.redis.pubsub()
        pubsub.subscribe(RESULTS_CHANNEL)

        for raw in pubsub.listen():
            if raw["type"] != "message":
                continue
            payload = json.loads(raw["data"])
            self.results.append(payload)
            print(f"{GREEN}[ResultCollector]{RESET} Collected result {payload['id']!r}: {payload['data']!r}")
            if len(self.results) >= expected_count:
                break

        pubsub.unsubscribe(RESULTS_CHANNEL)
        return self.results
