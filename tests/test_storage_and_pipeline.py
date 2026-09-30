"""Tests for storage adapters and landing idempotency."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from wrc_pipeline.pipelines import LandingPipeline
from wrc_pipeline.storage.minio_client import MinioStorage
from wrc_pipeline.storage.mongo import AsyncMongoStorage, MongoStorage

from .conftest import make_config


def make_item(content=b"raw html"):
    return {
        "identifier": "ADJ-0001",
        "title": "Decision",
        "description": "A decision",
        "published_date": "2024-01-10",
        "body": "Workplace Relations Commission",
        "source_url": "https://example.test/decision.html",
        "document_url": None,
        "partition_date": "2024-01",
        "partition_start": "2024-01-01",
        "partition_end": "2024-01-31",
        "source_identity": "identity-1",
        "raw_bytes": content,
        "source_content_type": "text/html",
        "file_extension": "html",
    }


class FakeCollection:
    def __init__(self):
        self.records = []

    def insert_one(self, record):
        self.records.append(record)


class FakeMongo:
    def __init__(self):
        self.landing_documents = FakeCollection()

    async def find_latest_landing(self, identity):
        records = [
            r
            for r in self.landing_documents.records
            if r["source_identity"] == identity
        ]
        return records[-1] if records else None

    async def insert_landing(self, record):
        self.landing_documents.insert_one(record)

    @staticmethod
    def now():
        return datetime.now(timezone.utc)


class FakeMinio:
    def __init__(self):
        self.uploads = []

    def object_exists(self, bucket, path):
        return any(upload[1] == path for upload in self.uploads)

    def upload_bytes(self, bucket, path, content, content_type):
        self.uploads.append((bucket, path, content, content_type))


class FakeSpider:
    def __init__(self):
        self.successes = 0
        self.failures = 0

    def record_success(self):
        self.successes += 1

    def record_failure(self, **context):
        self.failures += 1


def test_landing_pipeline_does_not_upload_unchanged_content_twice():
    pipeline = LandingPipeline(make_config())
    pipeline.mongo = FakeMongo()
    pipeline.minio = FakeMinio()
    spider = FakeSpider()

    asyncio.run(pipeline.process_item(make_item(), spider))
    asyncio.run(pipeline.process_item(make_item(), spider))

    assert len(pipeline.mongo.landing_documents.records) == 1
    assert len(pipeline.minio.uploads) == 1
    assert spider.successes == 2


def test_changed_content_gets_a_new_versioned_path():
    pipeline = LandingPipeline(make_config())
    pipeline.mongo = FakeMongo()
    pipeline.minio = FakeMinio()
    spider = FakeSpider()

    asyncio.run(pipeline.process_item(make_item(b"first"), spider))
    asyncio.run(pipeline.process_item(make_item(b"changed"), spider))

    assert len(pipeline.mongo.landing_documents.records) == 2
    assert len(pipeline.minio.uploads) == 2
    assert "--" in pipeline.minio.uploads[1][1]


def test_mongo_indexes_are_declared():
    config = make_config()
    client = MagicMock()
    database = MagicMock()
    client.__getitem__.return_value = database
    landing = MagicMock()
    processed = MagicMock()
    database.__getitem__.side_effect = [landing, processed]
    with patch("wrc_pipeline.storage.mongo.MongoClient", return_value=client):
        storage = MongoStorage(config)
        storage.ensure_indexes()
    assert landing.create_index.call_count == 3
    assert processed.create_index.call_count == 1


def test_async_mongo_storage_awaits_native_driver_operations():
    config = make_config()
    client = MagicMock()
    database = MagicMock()
    client.__getitem__.return_value = database
    landing = MagicMock()
    landing.create_index = AsyncMock()
    landing.find_one = AsyncMock(return_value={"file_hash": "hash"})
    landing.insert_one = AsyncMock()
    client.close = AsyncMock()
    database.__getitem__.side_effect = [landing]

    with patch(
        "wrc_pipeline.storage.mongo.AsyncMongoClient",
        return_value=client,
    ):
        storage = AsyncMongoStorage(config)
        asyncio.run(storage.ensure_indexes())
        assert asyncio.run(storage.find_latest_landing("identity")) == {
            "file_hash": "hash"
        }
        asyncio.run(storage.insert_landing({"source_identity": "identity"}))
        asyncio.run(storage.close())

    assert landing.create_index.await_count == 3
    landing.find_one.assert_awaited_once()
    landing.insert_one.assert_awaited_once()
    client.close.assert_awaited_once()


def test_minio_ensure_buckets_creates_missing_buckets():
    client = Mock()
    client.bucket_exists.return_value = False
    with patch("wrc_pipeline.storage.minio_client.Minio", return_value=client):
        storage = MinioStorage(make_config())
        storage.ensure_buckets()
    assert client.make_bucket.call_count == 2
