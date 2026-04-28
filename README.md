# philiprehberger-debounce

[![Tests](https://github.com/philiprehberger/py-debounce/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-debounce/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-debounce.svg)](https://pypi.org/project/philiprehberger-debounce/)
[![Last updated](https://img.shields.io/github/last-commit/philiprehberger/py-debounce)](https://github.com/philiprehberger/py-debounce/commits/main)

Debounce and throttle decorators for Python functions.

## Installation

```bash
pip install philiprehberger-debounce
```

## Usage

```python
from philiprehberger_debounce import debounce, throttle
```

### Debounce

Delay execution until a quiet period has passed. Each new call resets the timer.

```python
@debounce(0.5)
def on_resize(width, height):
    print(f"Resized to {width}x{height}")

on_resize(800, 600)
on_resize(1024, 768)  # cancels the previous call
# Only the last call executes after 0.5s
```

### Bounded debounce

Use `max_wait` to guarantee the function fires at most `max_wait` seconds after the *first* pending call, even if calls keep arriving and continuously reset the debounce timer. Mirrors lodash `debounce({ maxWait })` semantics.

```python
@debounce(0.5, max_wait=2.0)
def autosave(content):
    print(f"Saving: {content[:20]}...")

# Even with continuous edits, autosave fires at least every 2s.
for chunk in stream_keystrokes():
    autosave(chunk)
```

`max_wait` must be positive and `>= seconds`; otherwise `ValueError` is raised.

### Throttle

Limit a function to a fixed number of calls within a time window. Excess calls are silently dropped.

```python
@throttle(calls=3, per=1.0)
def send_request(data):
    print(f"Sending {data}")

for i in range(10):
    send_request(i)  # only the first 3 calls within 1s execute
```

## API

| Decorator | Parameter | Description |
|-----------|-----------|-------------|
| `debounce(seconds, *, leading=False, max_wait=None)` | `seconds` | Minimum quiet period (in seconds) before the function is invoked. Each new call cancels the previous pending invocation and restarts the timer. |
| | `leading` | If `True`, fire on the leading edge of the window instead of the trailing edge. Subsequent rapid calls are suppressed until `seconds` of silence have elapsed. |
| | `max_wait` | Optional upper bound (in seconds) on how long the function may be deferred from the first pending call. Must be positive and `>= seconds`. Mirrors lodash `debounce({ maxWait })`. |
| `throttle(calls, per)` | `calls` | Maximum number of allowed invocations within the sliding window. |
| | `per` | Length of the sliding window in seconds. Calls beyond `calls` within `per` are silently dropped. |

## Development

```bash
pip install -e .
python -m pytest tests/ -v
```

## Support

If you find this project useful:

⭐ [Star the repo](https://github.com/philiprehberger/py-debounce)

🐛 [Report issues](https://github.com/philiprehberger/py-debounce/issues?q=is%3Aissue+is%3Aopen+label%3Abug)

💡 [Suggest features](https://github.com/philiprehberger/py-debounce/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)

❤️ [Sponsor development](https://github.com/sponsors/philiprehberger)

🌐 [All Open Source Projects](https://philiprehberger.com/open-source-packages)

💻 [GitHub Profile](https://github.com/philiprehberger)

🔗 [LinkedIn Profile](https://www.linkedin.com/in/philiprehberger)

## License

[MIT](LICENSE)
