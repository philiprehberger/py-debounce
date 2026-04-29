"""Tests for debounce and throttle decorators."""

from __future__ import annotations

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
