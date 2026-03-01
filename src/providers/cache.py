"""
File-based caching layer for financial data.

Caches API responses as JSON files with TTL-based expiration.
Avoids redundant API calls across runs and during development.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from loguru import logger


class FileCache:
    """
    Simple file-based cache with TTL expiration.

    Cache structure:
        .cache/<provider>/<key_hash>.json

    Each cache file contains:
        {"timestamp": <epoch>, "ttl": <seconds>, "data": <payload>}
    """

    def __init__(self, cache_dir: str | Path = ".cache", ttl_hours: float = 24):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_hours * 3600
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, namespace: str, key: str) -> Path:
        """Generate a cache file path from namespace + key."""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        ns_dir = self.cache_dir / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir / f"{key_hash}.json"

    def get(self, namespace: str, key: str) -> Any | None:
        """
        Retrieve cached data if it exists and hasn't expired.

        Returns None on cache miss or expiry.
        """
        path = self._key_path(namespace, key)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)

            ts = entry.get("timestamp", 0)
            ttl = entry.get("ttl", self.ttl_seconds)
            if time.time() - ts > ttl:
                logger.debug(f"Cache expired: {namespace}/{key}")
                path.unlink(missing_ok=True)
                return None

            logger.debug(f"Cache hit: {namespace}/{key}")
            return entry.get("data")

        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Cache read error for {namespace}/{key}: {e}")
            path.unlink(missing_ok=True)
            return None

    def set(self, namespace: str, key: str, data: Any) -> None:
        """Store data in cache with current timestamp."""
        path = self._key_path(namespace, key)
        entry = {
            "timestamp": time.time(),
            "ttl": self.ttl_seconds,
            "data": data,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entry, f, default=str)
            logger.debug(f"Cache set: {namespace}/{key}")
        except OSError as e:
            logger.warning(f"Cache write error for {namespace}/{key}: {e}")

    def invalidate(self, namespace: str, key: str) -> None:
        """Remove a specific cache entry."""
        path = self._key_path(namespace, key)
        path.unlink(missing_ok=True)

    def clear(self, namespace: str | None = None) -> int:
        """
        Clear cache entries.

        Args:
            namespace: If given, clear only that namespace. Otherwise clear all.

        Returns:
            Number of entries removed.
        """
        count = 0
        if namespace:
            ns_dir = self.cache_dir / namespace
            if ns_dir.exists():
                for f in ns_dir.glob("*.json"):
                    f.unlink()
                    count += 1
        else:
            for f in self.cache_dir.rglob("*.json"):
                f.unlink()
                count += 1
        logger.info(f"Cache cleared: {count} entries removed")
        return count
