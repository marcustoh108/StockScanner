import time
import threading
from typing import Any, Callable

from app.config import CACHE_TTL_SECONDS

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def cached(key: str, ttl: int = CACHE_TTL_SECONDS) -> Callable:
    """Decorator-less helper: memoize the result of fn() under key for ttl seconds."""

    def wrapper(fn: Callable[[], Any]) -> Any:
        with _lock:
            hit = _store.get(key)
            if hit and (time.time() - hit[0]) < ttl:
                return hit[1]
        value = fn()
        with _lock:
            _store[key] = (time.time(), value)
        return value

    return wrapper
