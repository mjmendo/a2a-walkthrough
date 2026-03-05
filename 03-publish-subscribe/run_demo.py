"""
Demo runner for Pattern 3: Publish-Subscribe.

Starts three agents in separate threads, publishes 5 tasks, and waits for
all results to be collected before printing a summary.

Requires Redis on localhost:6379 (start with: docker-compose up redis).
"""

import threading
import time

import redis

from agents import PublisherAgent, ResultCollector, SubscriberAgent

CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"

TASK_COUNT = 5
SAMPLE_TASKS = [
    "analyse market trends",
    "process user feedback",
    "index search documents",
    "generate weekly report",
    "validate data integrity",
]


def main() -> None:
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    publisher = PublisherAgent(r)
    subscriber = SubscriberAgent(r)
    collector = ResultCollector(r)

    print(f"\n{CYAN}=== Publish-Subscribe Demo ==={RESET}")
    print(f"Tasks to publish: {TASK_COUNT}\n")

    # Start subscriber in a background thread
    subscriber_thread = threading.Thread(
        target=subscriber.start,
        args=(TASK_COUNT,),
        daemon=True,
    )

    # Start collector in a background thread
    collector_thread = threading.Thread(
        target=collector.collect,
        args=(TASK_COUNT,),
        daemon=True,
    )

    subscriber_thread.start()
    collector_thread.start()

    # Give subscriber/collector time to subscribe before publishing
    time.sleep(0.3)

    # Publish all tasks
    print(f"{CYAN}--- Publishing {TASK_COUNT} tasks ---{RESET}\n")
    publisher.publish_tasks(SAMPLE_TASKS)

    # Wait for both background threads to finish
    subscriber_thread.join(timeout=15)
    collector_thread.join(timeout=15)

    # Print summary
    print(f"\n{MAGENTA}{'='*50}{RESET}")
    print(f"{MAGENTA}  Summary: {len(collector.results)}/{TASK_COUNT} results collected{RESET}")
    print(f"{MAGENTA}{'='*50}{RESET}")
    for res in collector.results:
        print(f"  [{res['id']}] {res['data']}")
    print()


if __name__ == "__main__":
    main()
