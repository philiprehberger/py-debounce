"""Debounce and throttle decorators for Python functions."""

from __future__ import annotations

import threading
import time
from collections import deque
from functools import wraps
from typing import Any, Callable, TypeVar

__all__ = ["debounce", "throttle"]

F = TypeVar("F", bound=Callable[..., Any])


def debounce(seconds: float) -> Callable[[F], F]:
    """Delay function execution until *seconds* have passed since the last call.

    Each new call cancels the previous pending invocation and restarts the
    timer.  The decorated function is executed in a background thread once the
    delay elapses without interruption.

    Args:
        seconds: Minimum quiet period before the function is invoked.

    Returns:
        A decorator that wraps the target function with debounce logic.
    """

    def decorator(fn: F) -> F:
        timer: threading.Timer | None = None
        lock = threading.Lock()

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            nonlocal timer
            with lock:
                if timer is not None:
                    timer.cancel()
                timer = threading.Timer(seconds, fn, args=args, kwargs=kwargs)
                timer.daemon = True
                timer.start()

        return wrapper  # type: ignore[return-value]

    return decorator


def throttle(calls: int, per: float) -> Callable[[F], F]:
    """Limit a function to *calls* invocations within every *per* seconds.

    Invocations that exceed the limit are silently dropped.  The window is
    sliding: each call is timestamped and old timestamps are pruned on every
    invocation.

    Args:
        calls: Maximum number of allowed invocations in the window.
        per: Length of the sliding window in seconds.

    Returns:
        A decorator that wraps the target function with throttle logic.
    """

    def decorator(fn: F) -> F:
        timestamps: deque[float] = deque()
        lock = threading.Lock()

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            now = time.monotonic()
            with lock:
                # Remove timestamps outside the current window
                while timestamps and timestamps[0] <= now - per:
                    timestamps.popleft()

                if len(timestamps) >= calls:
                    return None

                timestamps.append(now)

            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
