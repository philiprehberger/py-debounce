# Changelog

## 0.6.0 (2026-10-30)

- Add `async def` support to `debounce` — the trailing call is scheduled with `loop.call_later` on the running event loop and runs as an `asyncio.Task`; the wrapper is a regular function returning `None`; `leading`, `max_wait`, `.cancel()`, `.flush()`, and `.is_pending()` keep working, and `.flush()` returns the started task
- Add `async def` support to `throttle` — the wrapper stays a coroutine function; allowed calls resolve to the result, dropped calls resolve to `None`
- Add `.reset()` and `.remaining()` methods on the throttle wrapper (thread-safe)
- Type `debounce` with `ParamSpec` so the wrapper is typed as returning `None`, matching runtime behavior
- Convert the README API table to the `Function / Class | Description` format, one row per function or method
- Add README usage sections for async functions and throttle helpers

## 0.5.0 (2026-06-15)

- Add `.is_pending()` method on the debounced wrapper — returns `True` while a trailing call is queued; useful for UI integration ("Saving…" indicators)
- Add package-card image to README

## 0.4.0 (2026-04-28)

- Add `.cancel()` and `.flush()` methods on the debounced wrapper — cancel discards a pending trailing call and resets leading-edge state; flush fires the pending call immediately

## 0.3.0 (2026-04-27)

- Add `max_wait` parameter to `debounce` decorator — guarantees the wrapped function fires at most `max_wait` seconds after the first pending call, even under continuous reset chains
- Validate `max_wait` arguments (must be positive and >= seconds)

## 0.2.0 (2026-04-04)

- Add `leading` parameter to debounce decorator for leading-edge execution

## 0.1.2 (2026-03-31)

- Standardize README to 3-badge format with emoji Support section
- Update CI checkout action to v5 for Node.js 24 compatibility
- Add GitHub issue templates, dependabot config, and PR template

## 0.1.1 (2026-03-22)

- Add badges to README
- Rename Install section to Installation in README
- Add Development section to README
- Add Changelog URL to project URLs
- Add `#readme` anchor to Homepage URL
- Add pytest and mypy configuration

## 0.1.0 (2026-03-21)

- Initial release
- `debounce(seconds)` decorator with timer cancellation
- `throttle(calls, per)` decorator with sliding window
