"""
Rate limiter with retry and exponential backoff.

Ensures polite API usage and handles transient failures.
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from loguru import logger

T = TypeVar("T")


class RateLimiter:
    """
    Token-bucket-style rate limiter.

    Ensures a minimum interval between calls.
    """

    def __init__(self, calls_per_second: float = 2.0):
        self.min_interval = 1.0 / calls_per_second
        self._last_call: float = 0.0

    def wait(self) -> None:
        """Block until the next call is allowed."""
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        self._last_call = time.time()


def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorator: retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retries (0 = no retry).
        backoff_factor: Multiplier for wait time between retries.
        exceptions: Tuple of exception types to catch and retry.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait = backoff_factor ** attempt
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__}: "
                            f"{e}. Waiting {wait:.1f}s..."
                        )
                        time.sleep(wait)
                    else:
                        logger.error(
                            f"All {max_retries} retries exhausted for {func.__name__}: {e}"
                        )
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
