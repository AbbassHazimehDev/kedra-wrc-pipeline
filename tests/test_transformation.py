"""Tests for HTML selection and rerunnable transformation."""

from datetime import datetime, timezone

from wrc_pipeline.transformation.transform import (
    extract_legal_html,
    transform_documents,
)

from .conftest import make_config


RAW_HTML = b"""
<html><body>
<header>Global header</header>
<nav>Navigation</nav>
<div class="content">
  <h1>Decision</h1>
  <p>Meaningful legal text.</p>
  <button>Print</button>
</div>
<footer>Global footer</footer>
</body></html>
"""


class FakeCollection:
    def __init__(self):
        self.records = []

    def find_one(self, query):
        return next(
            (
                r
                for r in self.records
                if r["transformation_identity"]
                == query["transformation_identity"]
            ),
            None,
        )

    def insert_one(self, record):
        self.records.append(record)


class FakeMongo:
    def __init__(self, records):
        self.records = records
        self.processed_documents = FakeCollection()

    def ensure_indexes(self):
        pass

    def find_landing_by_range(self, start, end):
        return self.records

    @staticmethod
    def now():
        return datetime.now(timezone.utc)


class FakeMinio:
    def __init__(self, content):
        self.content = content
        self.uploads = []

    def ensure_buckets(self):
        pass

    def download_bytes(self, bucket, path):
        return self.content

    def object_exists(self, bucket, path):
        return any(upload[1] == path for upload in self.uploads)

    def upload_bytes(self, bucket, path, content, content_type):
        self.uploads.append((bucket, path, content, content_type))


def make_record(extension="html"):
    return {
        "source_identity": "identity-1",
        "file_hash": "raw-hash",
        "identifier": "ADJ-0001",
        "title": "Decision",
        "description": "A decision",
        "published_date": "2024-01-10",
        "body": "Workplace Relations Commission",
        "source_url": "https://example.test/decision.html",
        "document_url": None,
        "partition_date": "2024-01",
        "file_extension": extension,
        "landing_bucket": "landing",
        "file_path": "landing/source.html",
        "source_content_type": (
            "text/html" if extension == "html" else "application/pdf"
        ),
    }


def test_extract_legal_html_removes_global_ui():
    output = extract_legal_html(RAW_HTML).decode()

    assert "Meaningful legal text." in output
    assert "Global header" not in output
    assert "Navigation" not in output
    assert "Print" not in output
    assert "Global footer" not in output


def test_transformation_is_idempotent_and_preserves_pdf_bytes():
    html_mongo = FakeMongo([make_record()])
    html_minio = FakeMinio(RAW_HTML)
    first = transform_documents(
        "2024-01-01", "2024-01-31", html_mongo, html_minio, make_config()
    )
    second = transform_documents(
        "2024-01-01", "2024-01-31", html_mongo, html_minio, make_config()
    )
    assert first == {"found": 1, "succeeded": 1, "skipped": 0, "failed": 0}
    assert second == {"found": 1, "succeeded": 0, "skipped": 1, "failed": 0}
    assert html_minio.uploads[0][1].endswith("/ADJ-0001.html")

    pdf_bytes = b"%PDF-1.7 original"
    pdf_mongo = FakeMongo([make_record("pdf")])
    pdf_minio = FakeMinio(pdf_bytes)
    transform_documents(
        "2024-01-01", "2024-01-31", pdf_mongo, pdf_minio, make_config()
    )
    assert pdf_minio.uploads[0][2] == pdf_bytes
    assert pdf_minio.uploads[0][1].endswith("/ADJ-0001.pdf")
