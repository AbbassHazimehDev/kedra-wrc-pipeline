"""Shared test fixtures."""

from wrc_pipeline.config import AppConfig


def make_config() -> AppConfig:
    """Return a safe in-memory configuration for unit tests."""
    return AppConfig(
        mongo_uri="mongodb://localhost:27017",
        mongo_database="test_database",
        mongo_landing_collection="landing_documents",
        mongo_processed_collection="processed_documents",
        minio_endpoint="localhost:9000",
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_secure=False,
        minio_landing_bucket="landing",
        minio_processed_bucket="processed",
        minio_landing_prefix="landing",
        minio_processed_prefix="processed",
        scrape_partition_months=1,
        scrape_retry_times=3,
        scrape_download_timeout=60,
        scrape_refresh_existing=False,
        wrc_search_url="https://example.test/en/search/?advance=true",
        wrc_user_agent="test-agent",
    )
