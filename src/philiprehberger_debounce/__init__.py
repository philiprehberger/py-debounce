"""Debounce and throttle decorators for Python functions."""

from __future__ import annotations

import asyncio
import inspect
import threading
import time
from collections import deque
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

__all__ = ["debounce", "throttle"]

F = TypeVar("F", bound=Callable[..., Any])
P = ParamSpec("P")


def debounce(
    seconds: float,
    *,
    leading: bool = False,
    max_wait: float | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, None]]:
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

    The returned wrapper exposes three control methods:

    - ``wrapper.cancel()`` — discard any pending trailing invocation and reset
      leading-edge state so the next call fires immediately.
    - ``wrapper.flush()`` — fire the pending trailing invocation immediately
      (no-op if nothing is pending).
    - ``wrapper.is_pending()`` — return whether a trailing call is queued.

    Coroutine functions (``async def``) are supported.  The wrapper is then a
    regular (non-async) function that returns ``None`` and must be called from
    inside a running event loop.  Instead of a background thread, the trailing
    invocation is scheduled with ``loop.call_later`` and runs as an
    ``asyncio.Task`` on that loop.  For coroutine functions ``flush()`` returns
    the created ``asyncio.Task`` (or ``None`` if nothing was pending) so the
    caller can await it.

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

    def decorator(fn: Callable[P, Any]) -> Callable[P, None]:
        if inspect.iscoroutinefunction(fn):
            return _debounce_async(fn, seconds, leading, max_wait)
        return _debounce_sync(fn, seconds, leading, max_wait)

    return decorator


def _debounce_sync(
    fn: Callable[..., Any],
    seconds: float,
    leading: bool,
    max_wait: float | None,
) -> Callable[..., None]:
    """Build the thread-based debounce wrapper for a regular function."""
    timer: threading.Timer | None = None
    lock = threading.Lock()
    may_call = True
    first_call_at: float | None = None
    pending: tuple[tuple[Any, ...], dict[str, Any]] | None = None

    def _reset_may_call() -> None:
        nonlocal may_call
        with lock:
            may_call = True

    def _fire_trailing(*args: Any, **kwargs: Any) -> None:
        nonlocal first_call_at, pending
        with lock:
            first_call_at = None
            pending = None
        fn(*args, **kwargs)

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        nonlocal timer, may_call, first_call_at, pending
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

            pending = (args, kwargs)

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
                pending = None
                fn(*args, **kwargs)
                return

            remaining_max = max_wait - elapsed
            delay = seconds if seconds < remaining_max else remaining_max
            timer = threading.Timer(delay, _fire_trailing, args=args, kwargs=kwargs)
            timer.daemon = True
            timer.start()

    def cancel() -> None:
        """Discard any pending trailing call and reset leading-edge state."""
        nonlocal timer, may_call, first_call_at, pending
        with lock:
            if timer is not None:
                timer.cancel()
                timer = None
            pending = None
            first_call_at = None
            may_call = True

    def flush() -> None:
        """Fire the pending trailing invocation immediately, if any."""
        nonlocal timer, first_call_at, pending
        with lock:
            if pending is None:
                return
            if timer is not None:
                timer.cancel()
                timer = None
            args, kwargs = pending
            pending = None
            first_call_at = None
        fn(*args, **kwargs)

    def is_pending() -> bool:
        """Return whether a trailing call is queued and not yet fired."""
        with lock:
            return pending is not None

    wrapper.cancel = cancel  # type: ignore[attr-defined]
    wrapper.flush = flush  # type: ignore[attr-defined]
    wrapper.is_pending = is_pending  # type: ignore[attr-defined]
    return wrapper


def _debounce_async(
    fn: Callable[..., Any],
    seconds: float,
    leading: bool,
    max_wait: float | None,
) -> Callable[..., None]:
    """Build the event-loop-based debounce wrapper for a coroutine function."""
    lock = threading.Lock()
    handle: asyncio.TimerHandle | None = None
    may_call = True
    first_call_at: float | None = None
    pending: tuple[asyncio.AbstractEventLoop, tuple[Any, ...], dict[str, Any]] | None = None
    tasks: set[asyncio.Task[Any]] = set()

    def _spawn(
        loop: asyncio.AbstractEventLoop,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> asyncio.Task[Any]:
        task: asyncio.Task[Any] = loop.create_task(fn(*args, **kwargs))
        # Keep a strong reference so the task is not garbage collected early.
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return task

    def _reset_may_call() -> None:
        nonlocal may_call, handle
        with lock:
            may_call = True
            handle = None

    def _fire_trailing() -> None:
        nonlocal handle, first_call_at, pending
        with lock:
            handle = None
            if pending is None:
                return
            loop, args, kwargs = pending
            pending = None
            first_call_at = None
        _spawn(loop, args, kwargs)

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        nonlocal handle, may_call, first_call_at, pending
        loop = asyncio.get_running_loop()
        with lock:
            if handle is not None:
                handle.cancel()
                handle = None

            if leading:
                should_call = may_call
                may_call = False
                handle = loop.call_later(seconds, _reset_may_call)
                if should_call:
                    _spawn(loop, args, kwargs)
                return

            pending = (loop, args, kwargs)

            if max_wait is None:
                handle = loop.call_later(seconds, _fire_trailing)
                return

            now = time.monotonic()
            if first_call_at is None:
                first_call_at = now

            elapsed = now - first_call_at
            if elapsed >= max_wait:
                # Upper bound already reached — fire immediately.
                first_call_at = None
                pending = None
                _spawn(loop, args, kwargs)
                return

            remaining_max = max_wait - elapsed
            delay = seconds if seconds < remaining_max else remaining_max
            handle = loop.call_later(delay, _fire_trailing)

    def cancel() -> None:
        """Discard any pending trailing call and reset leading-edge state."""
        nonlocal handle, may_call, first_call_at, pending
        with lock:
            if handle is not None:
                handle.cancel()
                handle = None
            pending = None
            first_call_at = None
            may_call = True

    def flush() -> asyncio.Task[Any] | None:
        """Start the pending trailing invocation now and return its task, if any."""
        nonlocal handle, first_call_at, pending
        with lock:
            if pending is None:
                return None
            if handle is not None:
                handle.cancel()
                handle = None
            loop, args, kwargs = pending
            pending = None
            first_call_at = None
        return _spawn(loop, args, kwargs)

    def is_pending() -> bool:
        """Return whether a trailing call is queued and not yet started."""
        with lock:
            return pending is not None

    wrapper.cancel = cancel  # type: ignore[attr-defined]
    wrapper.flush = flush  # type: ignore[attr-defined]
    wrapper.is_pending = is_pending  # type: ignore[attr-defined]
    return wrapper


def throttle(calls: int, per: float) -> Callable[[F], F]:
    """Limit a function to *calls* invocations within every *per* seconds.

    Invocations that exceed the limit are silently dropped and return ``None``.
    The window is sliding: each call is timestamped and old timestamps are
    pruned on every invocation.

    Coroutine functions (``async def``) are supported.  The wrapper is then
    itself a coroutine function: awaiting an allowed call returns the wrapped
    coroutine's result, and awaiting a dropped call returns ``None`` without
    running the wrapped function.  The slot is claimed when the returned
    coroutine starts running (normally the moment it is awaited).

    The returned wrapper exposes two helper methods:

    - ``wrapper.reset()`` — clear the window so the full quota is available.
    - ``wrapper.remaining()`` — number of calls still allowed in the current
      window.

    Args:
        calls: Maximum number of allowed invocations in the window.
        per: Length of the sliding window in seconds.

    Returns:
        A decorator that wraps the target function with throttle logic.
    """

    def decorator(fn: F) -> F:
        timestamps: deque[float] = deque()
        lock = threading.Lock()

        def _prune(now: float) -> None:
            # Remove timestamps outside the current window. Caller holds the lock.
            while timestamps and timestamps[0] <= now - per:
                timestamps.popleft()

        def _acquire() -> bool:
            now = time.monotonic()
            with lock:
                _prune(now)
                if len(timestamps) >= calls:
                    return False
                timestamps.append(now)
                return True

        wrapper: Callable[..., Any]
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not _acquire():
                    return None
                return await fn(*args, **kwargs)

            wrapper = async_wrapper
        else:

            @wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if not _acquire():
                    return None
                return fn(*args, **kwargs)

            wrapper = sync_wrapper

        def reset() -> None:
            """Clear the sliding window so the full quota is available again."""
            with lock:
                timestamps.clear()

        def remaining() -> int:
            """Return how many calls are still allowed in the current window."""
            now = time.monotonic()
            with lock:
                _prune(now)
                return max(0, calls - len(timestamps))

        setattr(wrapper, "reset", reset)
        setattr(wrapper, "remaining", remaining)
        return wrapper  # type: ignore[return-value]

    return decorator
