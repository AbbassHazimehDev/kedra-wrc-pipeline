"""Scrapy spider for all Bodies exposed by the WRC decisions search."""

import os
import re
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse

import scrapy
from scrapy import signals
from scrapy.exceptions import DropItem
from scrapy.http import Response

from wrc_pipeline.config import AppConfig
from wrc_pipeline.items import WrcDecisionItem
from wrc_pipeline.storage.mongo import MongoStorage
from wrc_pipeline.utils.dates import DatePartition, generate_partitions
from wrc_pipeline.utils.hashing import sha256_bytes
from wrc_pipeline.utils.logging import emit_event


WRC_BODIES = {
    "Employment Appeals Tribunal": "2",
    "Equality Tribunal": "1",
    "Labour Court": "3",
    "Workplace Relations Commission": "15376",
}


class DecisionsSpider(scrapy.Spider):
    """Search each WRC Body and follow every result's detail/document link."""

    name = "decisions"
    allowed_domains = ["workplacerelations.ie"]

    def __init__(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        refresh_existing: str = "false",
        *args: str,
        **kwargs: str,
    ) -> None:
        super().__init__(*args, **kwargs)
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")
        self.start_date = start_date
        self.end_date = end_date
        self.partition_months = int(os.getenv("SCRAPE_PARTITION_MONTHS", "1"))
        self.refresh_existing = refresh_existing.lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.search_url = os.getenv(
            "WRC_SEARCH_URL",
            "https://www.workplacerelations.ie/en/search/?advance=true",
        )
        self.partitions = generate_partitions(
            start_date, end_date, self.partition_months
        )
        self.mongo: MongoStorage | None = None
        self.records_found = 0
        self.records_succeeded = 0
        self.records_failed = 0
        self.records_skipped = 0
        self.expected_results = 0

    @classmethod
    def from_crawler(cls, crawler: scrapy.crawler.Crawler, *args: str, **kwargs: str):
        """Attach service storage and the spider-close summary signal."""
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.mongo = MongoStorage(AppConfig.from_env())
        spider.mongo.ensure_indexes()
        crawler.signals.connect(spider.closed, signal=signals.spider_closed)
        return spider

    def start_requests(self):
        """Start one search request for each partition and Body."""
        for partition in self.partitions:
            for body, body_value in WRC_BODIES.items():
                emit_event(
                    "search_started",
                    partition_date=partition.partition_date,
                    body=body,
                    start_date=partition.start_date.isoformat(),
                    end_date=partition.end_date.isoformat(),
                )
                yield scrapy.Request(
                    self.build_search_url(partition, body_value),
                    callback=self.parse_search,
                    errback=self.handle_request_failure,
                    meta={
                        "partition": partition,
                        "body": body,
                        "body_value": body_value,
                        "page_number": 1,
                        "record_context": {
                            "partition_date": partition.partition_date,
                            "body": body,
                        },
                    },
                )

    def build_search_url(
        self, partition: DatePartition, body_value: str, page_number: int | None = None
    ) -> str:
        """Build the verified WRC search query for one Body and partition."""
        params = {
            "decisions": "1",
            "from": partition.start_date.strftime("%d/%m/%Y"),
            "to": partition.end_date.strftime("%d/%m/%Y"),
            "legislationsub": "",
            "body": body_value,
        }
        if page_number and page_number > 1:
            params["pageNumber"] = str(page_number)
        return f"{self.search_url.split('?')[0]}?{urlencode(params)}"

    def parse_search(self, response: Response):
        """Parse one result page and queue the next page when present."""
        partition: DatePartition = response.meta["partition"]
        body = response.meta["body"]
        page_number = response.meta["page_number"]
        expected = self._result_count(response)
        if expected is not None and page_number == 1:
            self.expected_results += expected

        result_nodes = response.css("li.each-item")
        self.records_found += len(result_nodes)
        emit_event(
            "search_page",
            partition_date=partition.partition_date,
            body=body,
            page_number=page_number,
            records_found=len(result_nodes),
            expected_results=expected,
        )

        for node in result_nodes:
            record = self._parse_result(node, response, partition, body)
            if not record:
                self.record_failure(
                    partition_date=partition.partition_date,
                    body=body,
                    reason="result_missing_identifier_or_url",
                )
                continue

            if self.mongo and not self.refresh_existing:
                existing = self.mongo.find_latest_landing(record["source_identity"])
                if existing:
                    self.records_skipped += 1
                    emit_event(
                        "record_skipped_unchanged_check",
                        **self._context(record),
                    )
                    continue

            yield scrapy.Request(
                record["source_url"],
                callback=self.parse_detail,
                errback=self.handle_request_failure,
                meta={
                    "record": record,
                    "record_context": self._context(record),
                },
            )

        next_page = self._next_page(response, page_number)
        if next_page:
            yield scrapy.Request(
                response.urljoin(next_page),
                callback=self.parse_search,
                errback=self.handle_request_failure,
                meta={
                    **response.meta,
                    "page_number": page_number + 1,
                },
            )

    def parse_detail(self, response: Response):
        """Use a linked source document when present, otherwise land raw HTML."""
        record = response.meta["record"]
        record["title"] = self._detail_title(response)
        document_url = response.css("a.download::attr(href)").get()
        if document_url:
            record["document_url"] = response.urljoin(document_url)
            yield scrapy.Request(
                record["document_url"],
                callback=self.parse_document,
                errback=self.handle_request_failure,
                meta={
                    "record": record,
                    "record_context": self._context(record),
                },
            )
            return

        yield self._item_from_bytes(
            record,
            response.body,
            response.headers.get(b"Content-Type", b"text/html").decode(
                "latin-1"
            ),
            "html",
        )

    def parse_document(self, response: Response):
        """Determine a supported file type from headers, bytes, and URL."""
        record = response.meta["record"]
        content_type, extension = self._file_details(response)
        if extension not in {"pdf", "doc", "docx", "html"}:
            raise DropItem(f"Unsupported source document type: {content_type}")
        yield self._item_from_bytes(
            record, response.body, content_type, extension
        )

    def _item_from_bytes(
        self,
        record: dict[str, str | None],
        content: bytes,
        content_type: str,
        extension: str,
    ) -> WrcDecisionItem:
        """Build an item while keeping the source bytes untransformed."""
        return WrcDecisionItem(
            **record,
            raw_bytes=content,
            source_content_type=content_type.split(";", 1)[0].lower(),
            file_extension=extension,
        )

    def _parse_result(
        self, node, response: Response, partition: DatePartition, body: str
    ) -> dict[str, str | None] | None:
        identifier = node.css("h2.title a::attr(title)").get()
        if not identifier:
            identifier = node.css("h2.title a::text").get()
        detail_url = node.css("h2.title a::attr(href)").get()
        if not detail_url:
            detail_url = node.css("a.btn::attr(href)").get()
        if not identifier or not detail_url:
            return None

        description = node.css("p.description::attr(title)").get()
        if description is None:
            description = " ".join(
                part.strip() for part in node.css("p.description ::text").getall()
                if part.strip()
            ) or None
        published = node.css("span.date::text").get()
        published_iso = self._published_date(published)
        source_url = response.urljoin(detail_url)
        source_identity = sha256_bytes(f"{body}:{identifier}".encode("utf-8"))
        return {
            "identifier": identifier.strip(),
            "title": None,
            "description": description.strip() if description else None,
            "published_date": published_iso,
            "body": body,
            "source_url": source_url,
            "document_url": None,
            "partition_date": partition.partition_date,
            "partition_start": partition.start_date.isoformat(),
            "partition_end": partition.end_date.isoformat(),
            "source_identity": source_identity,
        }

    @staticmethod
    def _published_date(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()
        except ValueError:
            return value.strip()

    @staticmethod
    def _detail_title(response: Response) -> str | None:
        title = response.css("div.content h1::text").get()
        return " ".join(title.split()) if title else None

    @staticmethod
    def _result_count(response: Response) -> int | None:
        text = " ".join(response.css("div.searchhead::text").getall())
        match = re.search(r"of\s+(\d+)\s+results", text, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _next_page(response: Response, current_page: int) -> str | None:
        for href in response.css("ul.pager a::attr(href)").getall():
            query = parse_qs(urlparse(href).query)
            page = query.get("pageNumber", [None])[0]
            if page and int(page) == current_page + 1:
                return href
        return None

    @staticmethod
    def _file_details(response: Response) -> tuple[str, str]:
        content_type = response.headers.get(b"Content-Type", b"").decode(
            "latin-1"
        ).split(";", 1)[0].lower()
        path = urlparse(response.url).path.lower()
        body = response.body
        if body.startswith(b"%PDF") or "pdf" in content_type:
            return content_type or "application/pdf", "pdf"
        if "wordprocessingml.document" in content_type or path.endswith(".docx"):
            return content_type or "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
        if content_type == "application/msword" or path.endswith(".doc"):
            return content_type or "application/msword", "doc"
        if "html" in content_type or path.endswith((".html", ".htm")):
            return content_type or "text/html", "html"
        if body.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            return "text/html", "html"
        return content_type or "application/octet-stream", "bin"

    @staticmethod
    def _context(record: dict[str, str | None]) -> dict[str, str | None]:
        return {
            "partition_date": record.get("partition_date"),
            "body": record.get("body"),
            "identifier": record.get("identifier"),
            "url": record.get("document_url") or record.get("source_url"),
        }

    def record_success(self) -> None:
        """Count a record successfully landed by the item pipeline."""
        self.records_succeeded += 1

    def record_failure(self, **context: str | int | None) -> None:
        """Count and emit a record-level failure."""
        self.records_failed += 1
        emit_event("record_failed", **context)

    def handle_request_failure(self, failure):
        """Log final request failures after Scrapy retries are exhausted."""
        context = dict(failure.request.meta.get("record_context", {}))
        response = getattr(failure.value, "response", None)
        status_code = response.status if response is not None else None
        context.update(
            {
                "status_code": status_code,
                "reason": str(failure.value),
            }
        )
        if "identifier" in context:
            self.record_failure(**context)
        else:
            emit_event("request_failed", **context)

    def closed(self, reason: str) -> None:
        """Close storage and emit the complete run summary."""
        emit_event(
            "run_summary",
            reason=reason,
            expected_results=self.expected_results,
            records_found=self.records_found,
            records_succeeded=self.records_succeeded,
            records_failed=self.records_failed,
            records_skipped=self.records_skipped,
        )
        if self.mongo:
            self.mongo.close()
