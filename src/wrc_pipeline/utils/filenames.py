"""Safe filename helpers."""

import re


def safe_filename_component(value: str) -> str:
    """Keep identifiers readable while removing path and control characters."""
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" .")
    return cleaned or "unknown"
