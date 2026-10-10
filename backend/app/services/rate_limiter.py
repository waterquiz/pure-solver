import time
import threading
from collections import defaultdict
from typing import Dict, List, Optional
from backend.app.config import settings


class SlidingWindowRateLimiter:
    def __init__(self, limit: int = None, window_seconds: int = None):
        self.limit = limit or settings.RATE_LIMIT
        self.window = window_seconds or settings.RATE_LIMIT_WINDOW
        self._lock = threading.Lock()
        self._history: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, identifier: str) -> bool:
        """
        Returns True if request is within allowed rate limit,
        False if exceeded.
        """
        now = time.time()
        cutoff = now - self.window

        with self._lock:
            timestamps = self._history[identifier]
            # Prune timestamps older than window
            self._history[identifier] = [ts for ts in timestamps if ts > cutoff]

            if len(self._history[identifier]) >= self.limit:
                return False

            self._history[identifier].append(now)
            return True

    def reset(self, identifier: Optional[str] = None):
        """Resets rate limiting state (useful for tests)."""
        with self._lock:
            if identifier:
                self._history.pop(identifier, None)
            else:
                self._history.clear()


rate_limiter = SlidingWindowRateLimiter()
