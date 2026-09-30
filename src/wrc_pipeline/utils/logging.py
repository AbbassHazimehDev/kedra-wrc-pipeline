"""Small JSON-lines logger for run-level and record-level events."""

import json
from datetime import datetime, timezone
from typing import Any


def emit_event(event: str, **fields: Any) -> None:
    """Write ASCII-safe JSON events for Dagster and Windows log capture."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **{key: value for key, value in fields.items() if value is not None},
    }
    print(json.dumps(payload, default=str, ensure_ascii=True), flush=True)
