"""Debounce and throttle decorators for Python functions."""

from __future__ import annotations

import threading
import time
from collections import deque
from functools import wraps
from typing import Any, Callable, TypeVar

__all__ = ["debounce", "throttle"]

F = TypeVar("F", bound=Callable[..., Any])


def debounce(
    seconds: float,
    *,
    leading: bool = False,
    max_wait: float | None = None,
) -> Callable[[F], F]:
    """Delay function execution until *seconds* have passed since the last call.

    Each new call cancels the previous pending invocation and restarts the
    timer.  The decorated function is executed in a background thread once the
    delay elapses without interruption.

    When *leading* is ``True`` the function fires immediately on the first call,
    then suppresses subsequent calls until *seconds* have elapsed without a new
    invocation.

    When *max_wait* is provided, it guarantees the wrapped function fires at
    most ``max_wait`` seconds after the *first* pending call, even when calls
    keep arriving and continuously reset the debounce timer.  Mirrors lodash
    ``debounce({ maxWait })`` semantics.

    Args:
        seconds: Minimum quiet period before the function is invoked.
        leading: If ``True``, invoke on the leading edge instead of the
            trailing edge.
        max_wait: Optional upper bound (in seconds) on how long the function
            may be deferred from the first pending call.  Must be positive and
            ``>= seconds``.

    Returns:
        A decorator that wraps the target function with debounce logic.

    Raises:
        ValueError: If ``max_wait`` is not positive or is less than ``seconds``.
    """

    if max_wait is not None:
        if max_wait <= 0:
            raise ValueError("max_wait must be positive")
        if max_wait < seconds:
            raise ValueError("max_wait must be >= seconds")

    def decorator(fn: F) -> F:
        timer: threading.Timer | None = None
        lock = threading.Lock()
        may_call = True
        first_call_at: float | None = None

        def _reset_may_call() -> None:
            nonlocal may_call
            with lock:
                may_call = True

        def _fire_trailing(*args: Any, **kwargs: Any) -> None:
            nonlocal first_call_at
            with lock:
                first_call_at = None
            fn(*args, **kwargs)

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> None:
            nonlocal timer, may_call, first_call_at
            with lock:
                if timer is not None:
                    timer.cancel()

                if leading:
                    should_call = may_call
                    may_call = False
                    timer = threading.Timer(seconds, _reset_may_call)
                    timer.daemon = True
                    timer.start()
                    if should_call:
                        fn(*args, **kwargs)
                    return

                if max_wait is None:
                    timer = threading.Timer(seconds, _fire_trailing, args=args, kwargs=kwargs)
                    timer.daemon = True
                    timer.start()
                    return

                # max_wait branch
                now = time.monotonic()
                if first_call_at is None:
                    first_call_at = now

                elapsed = now - first_call_at
                if elapsed >= max_wait:
                    # Upper bound already reached — fire immediately.
                    first_call_at = None
                    fn(*args, **kwargs)
                    return

                remaining_max = max_wait - elapsed
                delay = seconds if seconds < remaining_max else remaining_max
                timer = threading.Timer(delay, _fire_trailing, args=args, kwargs=kwargs)
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
