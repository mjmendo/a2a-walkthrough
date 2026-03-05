"""
Blackboard — shared workspace backed by a Redis Hash.

The Blackboard is the central coordination mechanism: agents read what
others have written and contribute their own partial results. No agent
calls another directly; they only interact through this shared state.

Redis data model:
  HASH  "blackboard"        -> field/value pairs for content
  HASH  "blackboard:status" -> field/value pairs for per-key status flags
"""

from typing import Any


class Blackboard:
    """
    Shared workspace wrapping a Redis Hash.

    Two internal hashes are used:
      - ``blackboard``         stores content values written by agents.
      - ``blackboard:status``  stores status strings for each content key,
                               allowing agents to signal readiness without
                               overwriting content.
    """

    CONTENT_KEY = "blackboard"
    STATUS_KEY = "blackboard:status"

    def __init__(self, redis_client: Any):
        """
        Args:
            redis_client: A redis.Redis (or fakeredis.FakeRedis) instance
                          configured with decode_responses=True.
        """
        self.redis = redis_client

    def write(self, key: str, value: str) -> None:
        """Write a content value to the blackboard."""
        self.redis.hset(self.CONTENT_KEY, key, value)

    def read(self, key: str) -> str | None:
        """Read a single content value. Returns None if the key is absent."""
        return self.redis.hget(self.CONTENT_KEY, key)

    def read_all(self) -> dict[str, str]:
        """Return all content key/value pairs currently on the blackboard."""
        return self.redis.hgetall(self.CONTENT_KEY)

    def set_status(self, key: str, status: str) -> None:
        """Set the status for a content key (e.g. 'pending', 'done', 'error')."""
        self.redis.hset(self.STATUS_KEY, key, status)

    def get_status(self, key: str) -> str | None:
        """Get the status for a content key. Returns None if not set."""
        return self.redis.hget(self.STATUS_KEY, key)

    def clear(self) -> None:
        """Wipe all blackboard content and status — useful for tests."""
        self.redis.delete(self.CONTENT_KEY, self.STATUS_KEY)
