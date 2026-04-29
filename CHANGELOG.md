# Changelog

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
