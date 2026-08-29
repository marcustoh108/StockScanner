"""Simple in-memory sliding-window rate limiter, keyed per user.

Good enough for a single-instance deployment; if the backend is ever scaled
to multiple processes/instances, replace the in-memory dict with Redis
(INCR + EXPIRE) so limits are shared across instances.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, status

from app.auth import get_current_user
from app.models import User

_lock = threading.Lock()
_hits: dict[int, deque] = defaultdict(deque)

MAX_REQUESTS_PER_WINDOW = 60
WINDOW_SECONDS = 3600


def rate_limited_user(user: User = Depends(get_current_user)) -> User:
    now = time.time()
    with _lock:
        q = _hits[user.id]
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        if len(q) >= MAX_REQUESTS_PER_WINDOW:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Rate limit exceeded ({MAX_REQUESTS_PER_WINDOW} requests/hour). Try again later.",
            )
        q.append(now)
    return user
