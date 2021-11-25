# philiprehberger-debounce

[![Tests](https://github.com/philiprehberger/py-debounce/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-debounce/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-debounce.svg)](https://pypi.org/project/philiprehberger-debounce/)
[![License](https://img.shields.io/github/license/philiprehberger/py-debounce)](LICENSE)
[![Sponsor](https://img.shields.io/badge/sponsor-GitHub%20Sponsors-ec6cb9)](https://github.com/sponsors/philiprehberger)

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

| Decorator | Description |
|-----------|-------------|
| `debounce(seconds)` | Delays execution until `seconds` have elapsed since the last call. Cancels any pending invocation on each new call. |
| `throttle(calls, per)` | Limits the function to `calls` invocations per `per` seconds. Uses a sliding window. |

## Development

```bash
pip install -e .
python -m pytest tests/ -v
```

## License

MIT
