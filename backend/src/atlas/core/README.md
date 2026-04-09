# core/ — Cross-Cutting Infrastructure

Logging, settings, and security utilities. Imported by every layer; imports nothing above itself.

## Files

| File          | Purpose                                                                               |
| ------------- | ------------------------------------------------------------------------------------- |
| `logging.py`  | `configure_logging()` — structlog JSON (prod) / console (dev); `get_logger()` factory |
| `security.py` | Password hashing, token utilities (if present)                                        |

## Logging

```python
from atlas.core.logging import get_logger

logger = get_logger(__name__)

# Always use key-value pairs — never f-strings
logger.info("Ticker created", ticker="AAPL", shares=10.5)
logger.error("Polygon request failed", status=503, ticker="AAPL")
```

Output format:

- **Development:** human-readable coloured console
- **Production/Staging:** structured JSON (one object per line)

## Settings

```python
from atlas.config import get_settings

settings = get_settings()
settings.database_url       # str
settings.polygon_api_key    # str | None
settings.environment        # "development" | "staging" | "production"
settings.allowed_origins    # CSV string of CORS origins
```

`get_settings()` is LRU-cached — safe to call anywhere without performance impact.

## Layering rules

- `core/` may be imported by **every** layer.
- `core/` must **never** import from `api/`, `services/`, `models/`, or `schemas/`.
