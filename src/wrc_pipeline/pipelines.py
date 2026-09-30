"""Landing-zone item pipeline for MongoDB metadata and MinIO source bytes."""

from pymongo.errors import DuplicateKeyError
from scrapy.exceptions import DropItem
from scrapy.utils.asyncio import run_in_thread

from wrc_pipeline.config import AppConfig
from wrc_pipeline.storage.minio_client import MinioStorage
from wrc_pipeline.storage.mongo import AsyncMongoStorage
from wrc_pipeline.utils.filenames import safe_filename_component
from wrc_pipeline.utils.hashing import sha256_bytes
from wrc_pipeline.utils.logging import emit_event


class LandingPipeline:
    """Hash, deduplicate, and store unmodified source documents."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.from_env()
        self.mongo: AsyncMongoStorage | None = None
        self.minio: MinioStorage | None = None
        self.crawler = None

    @classmethod
    def from_crawler(cls, crawler):
        """Create the pipeline using the same environment as Scrapy."""
        pipeline = cls(AppConfig.from_env())
        pipeline.crawler = crawler
        return pipeline

    async def open_spider(self, spider=None) -> None:
        """Connect to both stores and initialize their configured buckets/indexes."""
        spider = spider or self.crawler.spider
        self.mongo = AsyncMongoStorage(self.config)
        await self.mongo.ensure_indexes()
        self.minio = MinioStorage(self.config)
        await run_in_thread(self.minio.ensure_buckets)

    async def close_spider(self, spider=None) -> None:
        """Release service clients when the crawl finishes."""
        if self.mongo:
            await self.mongo.close()
            self.mongo = None
            self.minio = None

    async def process_item(self, item, spider=None):
        """Store one item without blocking Scrapy's event loop."""
        spider = spider or self.crawler.spider
        if not self.mongo or not self.minio:
            raise DropItem("Landing pipeline is not open")

        try:
            content = item["raw_bytes"]
            file_hash = sha256_bytes(content)
            identity = item["source_identity"]
            existing = await self.mongo.find_latest_landing(identity)
            if existing and existing.get("file_hash") == file_hash:
                emit_event(
                    "record_unchanged",
                    **self._context(item),
                    file_hash=file_hash,
                    object_path=existing.get("file_path"),
                )
                self._record_success(spider)
                return item

            object_path = await self._object_path(item, file_hash, existing)
            bucket = self.config.minio_landing_bucket
            if not await run_in_thread(
                self.minio.object_exists, bucket, object_path
            ):
                await run_in_thread(
                    self.minio.upload_bytes,
                    bucket,
                    object_path,
                    content,
                    item["source_content_type"],
                )

            metadata = {
                key: value
                for key, value in item.items()
                if key != "raw_bytes"
            }
            metadata.update(
                {
                    "file_path": object_path,
                    "file_hash": file_hash,
                    "ingested_at": self.mongo.now(),
                    "landing_bucket": bucket,
                }
            )
            try:
                await self.mongo.insert_landing(metadata)
            except DuplicateKeyError:
                # Another concurrent request may have landed this exact hash
                # after the pre-check. The unique index makes that race safe.
                emit_event(
                    "record_unchanged",
                    **self._context(item),
                    file_hash=file_hash,
                    object_path=object_path,
                )
            else:
                emit_event(
                    "record_landed",
                    **self._context(item),
                    file_hash=file_hash,
                    object_path=object_path,
                )
            self._record_success(spider)
            return item
        except Exception as exc:
            context = self._context(item)
            emit_event(
                "record_failed",
                **context,
                url=item.get("document_url") or item.get("source_url"),
                reason=str(exc),
            )
            self._record_failure(spider, context, str(exc))
            raise DropItem(str(exc)) from exc

    async def _object_path(self, item, file_hash: str, existing) -> str:
        body = safe_filename_component(item["body"])
        identifier = safe_filename_component(item["identifier"])
        extension = item["file_extension"]
        prefix = self.config.minio_landing_prefix
        base = f"{prefix}/{body}/{item['partition_date']}/{identifier}.{extension}"
        base_exists = await run_in_thread(
            self.minio.object_exists,
            self.config.minio_landing_bucket,
            base,
        )
        if existing or base_exists:
            return (
                f"{prefix}/{body}/{item['partition_date']}/"
                f"{identifier}--{file_hash[:12]}.{extension}"
            )
        return base

    @staticmethod
    def _context(item) -> dict[str, str | None]:
        return {
            "partition_date": item.get("partition_date"),
            "body": item.get("body"),
            "identifier": item.get("identifier"),
        }

    @staticmethod
    def _record_success(spider) -> None:
        if hasattr(spider, "record_success"):
            spider.record_success()

    @staticmethod
    def _record_failure(spider, context, reason: str) -> None:
        if hasattr(spider, "record_failure"):
            spider.record_failure(**context, reason=reason)
