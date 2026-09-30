"""Tests for Dagster-safe structured logging."""

import json
from contextlib import redirect_stdout
from io import StringIO

from wrc_pipeline.utils.logging import emit_event


def test_json_events_are_ascii_safe_for_windows_log_capture():
    output = StringIO()
    with redirect_stdout(output):
        emit_event("test", description="Decision – résumé")

    line = output.getvalue().strip()
    assert line.encode("ascii")
    assert json.loads(line)["description"] == "Decision – résumé"
