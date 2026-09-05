"""Tests for exact-byte hashing and safe names."""

from io import BytesIO

from wrc_pipeline.utils.filenames import safe_filename_component
from wrc_pipeline.utils.hashing import sha256_bytes, sha256_stream


def test_same_bytes_have_same_sha256():
    assert sha256_bytes(b"decision") == sha256_stream(BytesIO(b"decision"))


def test_different_bytes_have_different_sha256():
    assert sha256_bytes(b"one") != sha256_bytes(b"two")


def test_filename_sanitization_removes_path_separators():
    assert safe_filename_component("UD893/2008: result") == "UD893_2008_ result"
