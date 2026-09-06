"""Transform Landing Zone HTML and copy source documents to Processed Zone."""

import argparse
from typing import Any

from bs4 import BeautifulSoup

from wrc_pipeline.config import AppConfig
from wrc_pipeline.storage.minio_client import MinioStorage
from wrc_pipeline.storage.mongo import MongoStorage
from wrc_pipeline.utils.dates import parse_date_range
from wrc_pipeline.utils.filenames import safe_filename_component
from wrc_pipeline.utils.hashing import sha256_bytes
from wrc_pipeline.utils.logging import emit_event


SUPPORTED_EXTENSIONS = {"pdf", "doc", "docx", "html"}


def extract_legal_html(raw_html: bytes) -> bytes:
    """Return a small HTML document containing only the site's content area."""
    soup = BeautifulSoup(raw_html, "html.parser")
    content = soup.select_one("div.content")
    if content is None:
        raise ValueError("Could not find the decision content container")

    for element in content.select(
        "script, style, noscript, nav, header, footer, form, button, "
        ".cookie, .cookie-bar, .searchbanner, .return-to-search, "
        ".hidden-print, .no-print"
    ):
        element.decompose()

    output = BeautifulSoup(
        "<!doctype html><html><head></head><body></body></html>",
        "html.parser",
    )
    output.head.append(output.new_tag("meta", charset="utf-8"))
    output.body.append(content)
    return output.encode("utf-8")


def transform_documents(
    start_date: str,
    end_date: str,
    mongo: MongoStorage | None = None,
    minio: MinioStorage | None = None,
    config: AppConfig | None = None,
) -> dict[str, int]:
    """Transform all landing records in an inclusive published-date range."""
    start, end = parse_date_range(start_date, end_date)
    config = config or AppConfig.from_env()
    owns_mongo = mongo is None
    mongo = mongo or MongoStorage(config)
    minio = minio or MinioStorage(config)
    mongo.ensure_indexes()
    minio.ensure_buckets()

    summary = {"found": 0, "succeeded": 0, "skipped": 0, "failed": 0}
    try:
        records = mongo.find_landing_by_range(start, end)
        summary["found"] = len(records)
        emit_event(
            "transformation_started",
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            records_found=len(records),
        )
        for record in records:
            try:
                _transform_one(record, mongo, minio, config)
                summary["succeeded"] += 1
            except AlreadyTransformed:
                summary["skipped"] += 1
            except Exception as exc:
                summary["failed"] += 1
                emit_event(
                    "transformation_failed",
                    partition_date=record.get("partition_date"),
                    body=record.get("body"),
                    identifier=record.get("identifier"),
                    url=record.get("source_url"),
                    reason=str(exc),
                )
        emit_event("transformation_summary", **summary)
        return summary
    finally:
        if owns_mongo:
            mongo.close()


class AlreadyTransformed(Exception):
    """Internal signal used for an idempotent transformation no-op."""


def _transform_one(
    record: dict[str, Any],
    mongo: MongoStorage,
    minio: MinioStorage,
    config: AppConfig,
) -> None:
    """Transform one landing record without changing its original metadata."""
    extension = record.get("file_extension")
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported landing file extension: {extension}")

    raw = minio.download_bytes(
        record["landing_bucket"], record["file_path"]
    )
    output = extract_legal_html(raw) if extension == "html" else raw
    output_hash = sha256_bytes(output)
    transformation_identity = (
        f"{record['source_identity']}:{record['file_hash']}"
    )
    existing = mongo.processed_documents.find_one(
        {"transformation_identity": transformation_identity}
    )
    if existing and existing.get("transformed_file_hash") == output_hash:
        emit_event(
            "transformation_unchanged",
            **_context(record),
            transformed_file_hash=output_hash,
            object_path=existing.get("transformed_file_path"),
        )
        raise AlreadyTransformed

    identifier = safe_filename_component(record["identifier"])
    body = safe_filename_component(record["body"])
    object_path = (
        f"{config.minio_processed_prefix}/{body}/{record['partition_date']}/"
        f"{record['file_hash'][:12]}/{identifier}.{extension}"
    )
    bucket = config.minio_processed_bucket
    if not minio.object_exists(bucket, object_path):
        content_type = "text/html" if extension == "html" else record.get(
            "source_content_type", "application/octet-stream"
        )
        minio.upload_bytes(bucket, object_path, output, content_type)

    metadata = {
        "source_identity": record["source_identity"],
        "transformation_identity": transformation_identity,
        "identifier": record["identifier"],
        "title": record.get("title"),
        "description": record.get("description"),
        "published_date": record.get("published_date"),
        "body": record.get("body"),
        "source_url": record.get("source_url"),
        "document_url": record.get("document_url"),
        "partition_date": record.get("partition_date"),
        "file_extension": extension,
        "landing_bucket": record["landing_bucket"],
        "landing_file_path": record["file_path"],
        "landing_file_hash": record["file_hash"],
        "processed_bucket": bucket,
        "transformed_file_path": object_path,
        "transformed_file_hash": output_hash,
        "transformed_at": mongo.now(),
    }
    mongo.processed_documents.insert_one(metadata)
    emit_event(
        "record_transformed",
        **_context(record),
        transformed_file_hash=output_hash,
        object_path=object_path,
    )


def _context(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "partition_date": record.get("partition_date"),
        "body": record.get("body"),
        "identifier": record.get("identifier"),
    }


def main(argv: list[str] | None = None) -> int:
    """Run transformation from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args(argv)
    summary = transform_documents(args.start_date, args.end_date)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
