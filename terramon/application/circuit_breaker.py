"""
Circuit breaker for external API calls (LLM, FAL, HF).

Simple state machine:

    CLOSED ──(3 consecutive failures)──▶ OPEN
    OPEN   ──(60s cooldown elapsed)─────▶ HALF_OPEN
    HALF_OPEN ──(success)───────────────▶ CLOSED
    HALF_OPEN ──(failure)───────────────▶ OPEN

Thread-safe via threading.Lock.
"""

from __future__ import annotations

import time
import threading
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a call is rejected because the circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """State machine: CLOSED → OPEN (3 failures) → HALF_OPEN (after 60s) → CLOSED/OPEN."""

    def __init__(self, max_failures: int = 3, cooldown: float = 60.0, name: str = ""):
        self._max_failures = max_failures
        self._cooldown = cooldown
        self._name = name or "CircuitBreaker"
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "CLOSED"
        self._lock = threading.Lock()

    # ── Public properties ────────────────────────────────────────────

    @property
    def state(self) -> str:
        """Current state (CLOSED / OPEN / HALF_OPEN).

        Automatically transitions OPEN → HALF_OPEN when cooldown expires.
        """
        with self._lock:
            if self._state == "OPEN" and time.monotonic() - self._last_failure_time >= self._cooldown:
                self._state = "HALF_OPEN"
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    @property
    def is_available(self) -> bool:
        """True if the circuit allows calls (CLOSED or HALF_OPEN)."""
        return self.state != "OPEN"

    # ── Public API ───────────────────────────────────────────────────

    def on_success(self) -> None:
        """Record a success: reset failure count, transition to CLOSED."""
        with self._lock:
            self._failure_count = 0
            self._state = "CLOSED"

    def on_failure(self) -> None:
        """Record a failure: increment count, transition to OPEN if threshold reached."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self._max_failures:
                self._state = "OPEN"
                print(
                    f"[{self._name}] Circuit breaker TRIPPED "
                    f"({self._failure_count} failures, cooldown={self._cooldown}s)"
                )

    def call(self, fn: Callable[..., T], *args, **kwargs) -> T:
        """Call *fn* with circuit-breaker protection.

        - If the circuit is OPEN: raises CircuitBreakerOpenError immediately.
        - If the call succeeds: resets failure count, returns result.
        - If the call raises: increments failure count, re-raises.

        Use this for a clean single-call pattern. For retry loops, use
        on_success() / on_failure() manually.
        """
        if not self.is_available:
            raise CircuitBreakerOpenError(
                f"[{self._name}] Circuit breaker is OPEN — call rejected"
            )

        try:
            result = fn(*args, **kwargs)
            self.on_success()
            return result
        except BaseException:
            self.on_failure()
            raise

    def reset(self) -> None:
        """Force-reset the circuit breaker to CLOSED (for testing)."""
        with self._lock:
            self._failure_count = 0
            self._state = "CLOSED"

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker '{self._name}' "
            f"state={self.state} "
            f"failures={self.failure_count}/{self._max_failures}>"
        )
