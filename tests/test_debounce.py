"""Tests for debounce and throttle decorators."""

from __future__ import annotations

import asyncio
import inspect
import threading
import time

import pytest

from philiprehberger_debounce import debounce, throttle


def test_debounce_delays_execution() -> None:
    """The decorated function should not fire until the delay elapses."""
    results: list[int] = []
    event = threading.Event()

    @debounce(0.1)
    def append(value: int) -> None:
        results.append(value)
        event.set()

    append(1)
    # Should not have executed yet
    assert results == []

    event.wait(timeout=0.5)
    assert results == [1]


def test_debounce_cancels_previous() -> None:
    """Rapid calls should cancel earlier invocations, only the last fires."""
    results: list[int] = []
    event = threading.Event()

    @debounce(0.1)
    def append(value: int) -> None:
        results.append(value)
        event.set()

    append(1)
    append(2)
    append(3)

    event.wait(timeout=0.5)
    # Only the last call should have executed
    assert results == [3]


def test_throttle_limits_calls() -> None:
    """Calls beyond the limit within the window should be dropped."""
    results: list[int] = []

    @throttle(calls=2, per=1.0)
    def append(value: int) -> None:
        results.append(value)

    append(1)
    append(2)
    append(3)  # should be dropped

    assert results == [1, 2]


def test_throttle_allows_after_window() -> None:
    """After the window expires, calls should be allowed again."""
    results: list[int] = []

    @throttle(calls=1, per=0.1)
    def append(value: int) -> None:
        results.append(value)

    append(1)
    append(2)  # dropped
    assert results == [1]

    time.sleep(0.15)

    append(3)
    assert results == [1, 3]


def test_debounce_leading_fires_immediately() -> None:
    """Leading mode should fire on first call."""
    results: list[int] = []

    @debounce(0.1, leading=True)
    def append(value: int) -> None:
        results.append(value)

    append(1)
    assert results == [1]


def test_debounce_leading_ignores_subsequent() -> None:
    """Leading mode should ignore rapid subsequent calls."""
    results: list[int] = []

    @debounce(0.1, leading=True)
    def append(value: int) -> None:
        results.append(value)

    append(1)
    append(2)
    append(3)
    assert results == [1]


class TestMaxWait:
    """Tests for the ``max_wait`` parameter (lodash-style upper bound)."""

    def test_without_max_wait_resets_indefinitely(self) -> None:
        """Without max_wait, a continuous reset chain prevents firing."""
        results: list[int] = []

        @debounce(0.1)
        def append(value: int) -> None:
            results.append(value)

        # Reset the timer continuously for ~0.4s — far longer than the 0.1s
        # debounce window — and confirm nothing fires while resets continue.
        deadline = time.monotonic() + 0.4
        i = 0
        while time.monotonic() < deadline:
            append(i)
            i += 1
            time.sleep(0.05)

        # No fires yet because every call reset the timer.
        assert results == []

    def test_max_wait_fires_at_upper_bound(self) -> None:
        """With max_wait, continuous resets still fire within the bound."""
        results: list[int] = []

        @debounce(0.1, max_wait=0.3)
        def append(value: int) -> None:
            results.append(value)

        deadline = time.monotonic() + 0.5
        i = 0
        while time.monotonic() < deadline:
            append(i)
            i += 1
            time.sleep(0.05)

        # Wait briefly for any in-flight timer thread to land.
        time.sleep(0.2)

        # At least one fire must have occurred within the max_wait bound,
        # but not many — typical jitter allows 1-3.
        assert len(results) >= 1
        assert len(results) <= 3

    def test_first_call_at_resets_after_fire(self) -> None:
        """A second batch of calls after a fire also fires at max_wait."""
        results: list[int] = []

        @debounce(0.1, max_wait=0.3)
        def append(value: int) -> None:
            results.append(value)

        # Batch 1
        deadline = time.monotonic() + 0.5
        i = 0
        while time.monotonic() < deadline:
            append(i)
            i += 1
            time.sleep(0.05)

        time.sleep(0.2)
        first_batch_count = len(results)
        assert first_batch_count >= 1

        # Quiet pause — let any pending timer drain.
        time.sleep(0.3)

        # Batch 2
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            append(i)
            i += 1
            time.sleep(0.05)

        time.sleep(0.2)
        # Second batch must have produced additional fire(s).
        assert len(results) > first_batch_count

    def test_max_wait_zero_raises(self) -> None:
        """max_wait <= 0 must raise ValueError."""
        with pytest.raises(ValueError):
            debounce(0.1, max_wait=0.0)

        with pytest.raises(ValueError):
            debounce(0.1, max_wait=-0.5)

    def test_max_wait_less_than_seconds_raises(self) -> None:
        """max_wait < seconds is meaningless and must raise ValueError."""
        with pytest.raises(ValueError):
            debounce(0.5, max_wait=0.2)


class TestCancelAndFlush:
    """Tests for the ``cancel()`` and ``flush()`` control methods."""

    def test_cancel_drops_pending_call(self) -> None:
        results: list[int] = []

        @debounce(0.2)
        def append(value: int) -> None:
            results.append(value)

        append(1)
        append.cancel()  # type: ignore[attr-defined]
        time.sleep(0.4)

        assert results == []

    def test_cancel_then_call_fires_normally(self) -> None:
        results: list[int] = []
        event = threading.Event()

        @debounce(0.1)
        def append(value: int) -> None:
            results.append(value)
            event.set()

        append(1)
        append.cancel()  # type: ignore[attr-defined]
        append(2)
        event.wait(timeout=0.5)
        assert results == [2]

    def test_flush_fires_pending_immediately(self) -> None:
        results: list[int] = []

        @debounce(1.0)
        def append(value: int) -> None:
            results.append(value)

        append(7)
        assert results == []
        append.flush()  # type: ignore[attr-defined]
        assert results == [7]

    def test_flush_when_nothing_pending_is_noop(self) -> None:
        results: list[int] = []

        @debounce(0.1)
        def append(value: int) -> None:
            results.append(value)

        append.flush()  # type: ignore[attr-defined]
        assert results == []

    def test_cancel_resets_leading_state(self) -> None:
        results: list[int] = []

        @debounce(0.2, leading=True)
        def append(value: int) -> None:
            results.append(value)

        append(1)
        append(2)  # suppressed by leading
        assert results == [1]

        append.cancel()  # type: ignore[attr-defined]
        append(3)  # leading state reset → fires
        assert results == [1, 3]


class TestIsPending:
    def test_false_on_fresh_wrapper(self) -> None:
        @debounce(0.1)
        def fn(*args: object) -> None: ...

        assert fn.is_pending() is False  # type: ignore[attr-defined]

    def test_true_after_call_within_window(self) -> None:
        @debounce(0.1)
        def fn(*args: object) -> None: ...

        fn("a")
        assert fn.is_pending() is True  # type: ignore[attr-defined]
        fn.cancel()  # type: ignore[attr-defined]

    def test_false_after_cancel(self) -> None:
        @debounce(0.1)
        def fn(*args: object) -> None: ...

        fn("a")
        fn.cancel()  # type: ignore[attr-defined]
        assert fn.is_pending() is False  # type: ignore[attr-defined]

    def test_false_after_flush(self) -> None:
        @debounce(0.1)
        def fn(*args: object) -> None: ...

        fn("a")
        fn.flush()  # type: ignore[attr-defined]
        assert fn.is_pending() is False  # type: ignore[attr-defined]

    def test_false_after_natural_fire(self) -> None:
        @debounce(0.05)
        def fn(*args: object) -> None: ...

        fn("a")
        time.sleep(0.1)
        assert fn.is_pending() is False  # type: ignore[attr-defined]


class TestAsyncDebounce:
    """Tests for debouncing ``async def`` functions."""

    def test_wrapper_returns_none_and_fires_once(self) -> None:
        results: list[int] = []

        @debounce(0.02)
        async def append(value: int) -> None:
            results.append(value)

        async def main() -> None:
            assert append(1) is None
            append(2)
            append(3)
            assert results == []
            await asyncio.sleep(0.1)

        asyncio.run(main())
        assert results == [3]

    def test_is_pending_and_cancel(self) -> None:
        results: list[int] = []

        @debounce(0.02)
        async def append(value: int) -> None:
            results.append(value)

        async def main() -> None:
            assert append.is_pending() is False  # type: ignore[attr-defined]
            append(1)
            assert append.is_pending() is True  # type: ignore[attr-defined]
            append.cancel()  # type: ignore[attr-defined]
            assert append.is_pending() is False  # type: ignore[attr-defined]
            await asyncio.sleep(0.08)

        asyncio.run(main())
        assert results == []

    def test_is_pending_false_after_natural_fire(self) -> None:
        @debounce(0.01)
        async def fn() -> None: ...

        async def main() -> None:
            fn()
            await asyncio.sleep(0.06)
            assert fn.is_pending() is False  # type: ignore[attr-defined]

        asyncio.run(main())

    def test_flush_returns_awaitable_task(self) -> None:
        results: list[int] = []

        @debounce(10.0)
        async def append(value: int) -> int:
            results.append(value)
            return value * 2

        async def main() -> None:
            append(4)
            task = append.flush()  # type: ignore[attr-defined]
            assert task is not None
            assert await task == 8
            assert append.flush() is None  # type: ignore[attr-defined]

        asyncio.run(main())
        assert results == [4]

    def test_leading_fires_immediately_and_suppresses(self) -> None:
        results: list[int] = []

        @debounce(0.05, leading=True)
        async def append(value: int) -> None:
            results.append(value)

        async def main() -> None:
            append(1)
            append(2)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert results == [1]
            append.cancel()  # type: ignore[attr-defined]
            append(3)
            await asyncio.sleep(0.01)

        asyncio.run(main())
        assert results == [1, 3]

    def test_leading_allows_again_after_quiet_period(self) -> None:
        results: list[int] = []

        @debounce(0.02, leading=True)
        async def append(value: int) -> None:
            results.append(value)

        async def main() -> None:
            append(1)
            await asyncio.sleep(0.08)
            append(2)
            await asyncio.sleep(0.01)

        asyncio.run(main())
        assert results == [1, 2]

    def test_max_wait_bounds_reset_chain(self) -> None:
        results: list[int] = []

        @debounce(0.05, max_wait=0.1)
        async def append(value: int) -> None:
            results.append(value)

        async def main() -> None:
            # Reset every 10ms for ~0.3s; without max_wait nothing would fire.
            for i in range(30):
                append(i)
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.15)

        asyncio.run(main())
        assert len(results) >= 2
        assert results == sorted(results)

    def test_requires_running_loop(self) -> None:
        @debounce(0.01)
        async def fn() -> None: ...

        with pytest.raises(RuntimeError):
            fn()

    def test_sync_function_unaffected(self) -> None:
        @debounce(0.01)
        def fn() -> None: ...

        assert not inspect.iscoroutinefunction(fn)
        assert fn.flush() is None  # type: ignore[attr-defined]


class TestAsyncThrottle:
    """Tests for throttling ``async def`` functions."""

    def test_allowed_calls_return_result_dropped_return_none(self) -> None:
        @throttle(calls=2, per=10.0)
        async def double(value: int) -> int:
            return value * 2

        async def main() -> list[int | None]:
            return [await double(1), await double(2), await double(3)]

        assert inspect.iscoroutinefunction(double)
        assert asyncio.run(main()) == [2, 4, None]

    def test_dropped_call_does_not_run(self) -> None:
        results: list[int] = []

        @throttle(calls=1, per=10.0)
        async def append(value: int) -> None:
            results.append(value)

        async def main() -> None:
            await append(1)
            await append(2)

        asyncio.run(main())
        assert results == [1]

    def test_reset_and_remaining(self) -> None:
        @throttle(calls=2, per=10.0)
        async def fn() -> str:
            return "ok"

        async def main() -> None:
            assert fn.remaining() == 2  # type: ignore[attr-defined]
            await fn()
            assert fn.remaining() == 1  # type: ignore[attr-defined]
            await fn()
            assert await fn() is None
            fn.reset()  # type: ignore[attr-defined]
            assert fn.remaining() == 2  # type: ignore[attr-defined]
            assert await fn() == "ok"

        asyncio.run(main())


class TestThrottleHelpers:
    """Tests for ``reset()`` and ``remaining()`` on sync throttle wrappers."""

    def test_remaining_counts_down(self) -> None:
        @throttle(calls=3, per=10.0)
        def fn() -> None: ...

        assert fn.remaining() == 3  # type: ignore[attr-defined]
        fn()
        fn()
        assert fn.remaining() == 1  # type: ignore[attr-defined]
        fn()
        fn()  # dropped
        assert fn.remaining() == 0  # type: ignore[attr-defined]

    def test_remaining_recovers_after_window(self) -> None:
        @throttle(calls=1, per=0.05)
        def fn() -> None: ...

        fn()
        assert fn.remaining() == 0  # type: ignore[attr-defined]
        time.sleep(0.1)
        assert fn.remaining() == 1  # type: ignore[attr-defined]

    def test_reset_restores_quota(self) -> None:
        results: list[int] = []

        @throttle(calls=1, per=10.0)
        def append(value: int) -> None:
            results.append(value)

        append(1)
        append(2)  # dropped
        append.reset()  # type: ignore[attr-defined]
        append(3)
        assert results == [1, 3]

    def test_concurrent_calls_are_counted(self) -> None:
        @throttle(calls=1000, per=10.0)
        def fn() -> None: ...

        def worker() -> None:
            for _ in range(100):
                fn()
                fn.remaining()  # type: ignore[attr-defined]

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert fn.remaining() == 500  # type: ignore[attr-defined]
        fn.reset()  # type: ignore[attr-defined]
        assert fn.remaining() == 1000  # type: ignore[attr-defined]
