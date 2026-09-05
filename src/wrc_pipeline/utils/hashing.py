"""SHA-256 helpers for exact stored bytes."""

import hashlib
from typing import BinaryIO


def sha256_bytes(content: bytes) -> str:
    """Return the SHA-256 hex digest of bytes."""
    return hashlib.sha256(content).hexdigest()


def sha256_stream(stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
    """Hash a binary stream incrementally from its current position."""
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(chunk_size), b""):
        digest.update(chunk)
    return digest.hexdigest()
