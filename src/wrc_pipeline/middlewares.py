"""Downloader middleware for non-blocking pre-download idempotency checks."""

from __future__ import annotations

from scrapy.exceptions import IgnoreRequest
from scrapy.http import Request

from wrc_pipeline.config import AppConfig
from wrc_pipeline.storage.mongo import AsyncMongoStorage
from wrc_pipeline.utils.logging import emit_event


class ExistingRecordMiddleware:
    """Skip known records before download without blocking Scrapy's event loop."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.from_env()
        self.mongo: AsyncMongoStorage | None = None

    @classmethod
    def from_crawler(cls, crawler):
        """Build the middleware from the same environment as the spider."""
        return cls(AppConfig.from_env())

    async def open_spider(self, spider) -> None:
        """Create the Mongo client before the first request is scheduled."""
        self.mongo = AsyncMongoStorage(self.config)

    async def process_request(
        self, request: Request, spider
    ) -> None:
        """Skip an already-landed detail request before the HTTP download."""
        if not request.meta.get("dedupe_before_download"):
            return
        if getattr(spider, "refresh_existing", False) or not self.mongo:
            return

        record = request.meta.get("record", {})
        source_identity = record.get("source_identity")
        if not source_identity:
            return

        existing = await self.mongo.find_latest_landing(source_identity)
        if not existing:
            return

        context = dict(request.meta.get("record_context", {}))
        context.setdefault("url", request.url)
        request.meta["existing_record_skipped"] = True
        spider.records_skipped += 1
        emit_event("record_skipped_unchanged_check", **context)
        raise IgnoreRequest("Record already exists in the Landing Zone")

    async def close_spider(self, spider) -> None:
        """Close the Mongo client after all requests finish."""
        if self.mongo:
            await self.mongo.close()
            self.mongo = None
