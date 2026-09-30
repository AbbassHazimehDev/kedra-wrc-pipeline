"""Tests for pre-download idempotency behavior."""

import asyncio
from types import SimpleNamespace

import pytest
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Request

from wrc_pipeline.middlewares import ExistingRecordMiddleware

from .conftest import make_config


class FakeMongo:
    def __init__(self, existing=None):
        self.existing = existing
        self.lookups = []

    async def find_latest_landing(self, source_identity):
        self.lookups.append(source_identity)
        return self.existing

    async def close(self):
        pass


def make_request():
    return Request(
        "https://example.test/detail",
        meta={
            "dedupe_before_download": True,
            "record": {"source_identity": "identity-1"},
            "record_context": {
                "body": "Workplace Relations Commission",
                "identifier": "ADJ-0001",
            },
        },
    )


def test_existing_record_is_skipped_before_download():
    middleware = ExistingRecordMiddleware(make_config())
    middleware.mongo = FakeMongo(existing={"file_hash": "hash"})
    spider = SimpleNamespace(refresh_existing=False, records_skipped=0)
    request = make_request()

    with pytest.raises(IgnoreRequest):
        asyncio.run(middleware.process_request(request, spider))

    assert middleware.mongo.lookups == ["identity-1"]
    assert request.meta["existing_record_skipped"] is True
    assert spider.records_skipped == 1


def test_refresh_existing_bypasses_pre_download_lookup():
    middleware = ExistingRecordMiddleware(make_config())
    middleware.mongo = FakeMongo(existing={"file_hash": "hash"})
    spider = SimpleNamespace(refresh_existing=True, records_skipped=0)

    assert asyncio.run(middleware.process_request(make_request(), spider)) is None
    assert middleware.mongo.lookups == []
