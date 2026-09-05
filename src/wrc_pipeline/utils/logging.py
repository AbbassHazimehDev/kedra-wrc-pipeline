"""Small JSON-lines logger for run-level and record-level events."""

import json
from datetime import datetime, timezone
from typing import Any


def emit_event(event: str, **fields: Any) -> None:
    """Write one machine-readable event to stdout."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **{key: value for key, value in fields.items() if value is not None},
    }
    print(json.dumps(payload, default=str, ensure_ascii=False), flush=True)
