"""
Rate limiting for API calls.

Prevents exceeding API rate limits and manages request throttling.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, Optional


class RateLimiter:
    """Rate limiter for API calls."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: Optional[int] = None,
        requests_per_day: Optional[int] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour (optional)
            requests_per_day: Max requests per day (optional)
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day

        self.lock = Lock()
        self.request_times: Dict[str, list] = defaultdict(list)

    def wait_if_needed(self, key: str = "default"):
        """
        Wait if rate limit would be exceeded.

        Args:
            key: Rate limit key (for per-endpoint limiting)
        """
        with self.lock:
            now = time.time()
            times = self.request_times[key]

            # Remove old entries
            times[:] = [t for t in times if now - t < 3600]  # Keep last hour

            # Check per-minute limit
            recent = [t for t in times if now - t < 60]
            if len(recent) >= self.requests_per_minute:
                # Wait until oldest request is > 1 minute old
                wait_time = 60 - (now - min(recent)) + 0.1
                if wait_time > 0:
                    time.sleep(wait_time)
                    now = time.time()

            # Check per-hour limit
            if self.requests_per_hour:
                hour_recent = [t for t in times if now - t < 3600]
                if len(hour_recent) >= self.requests_per_hour:
                    wait_time = 3600 - (now - min(hour_recent)) + 0.1
                    if wait_time > 0:
                        time.sleep(wait_time)
                        now = time.time()

            # Check per-day limit
            if self.requests_per_day:
                day_recent = [t for t in times if now - t < 86400]
                if len(day_recent) >= self.requests_per_day:
                    wait_time = 86400 - (now - min(day_recent)) + 0.1
                    if wait_time > 0:
                        time.sleep(wait_time)
                        now = time.time()

            # Record this request
            times.append(now)

    def reset(self, key: Optional[str] = None):
        """Reset rate limit counters."""
        with self.lock:
            if key:
                self.request_times[key].clear()
            else:
                self.request_times.clear()
