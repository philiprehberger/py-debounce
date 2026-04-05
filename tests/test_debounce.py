"""Tests for debounce and throttle decorators."""

from __future__ import annotations

import threading
import time

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
