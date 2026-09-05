"""Environment-backed application configuration."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def _as_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration shared by ingestion and transformation."""

    mongo_uri: str
    mongo_database: str
    mongo_landing_collection: str
    mongo_processed_collection: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool
    minio_landing_bucket: str
    minio_processed_bucket: str
    scrape_partition_months: int
    scrape_retry_times: int
    scrape_download_timeout: int
    scrape_refresh_existing: bool
    wrc_search_url: str
    wrc_user_agent: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load required service settings and optional scraping settings."""
        load_dotenv()
        return cls(
            mongo_uri=_required("MONGO_URI"),
            mongo_database=_required("MONGO_DATABASE"),
            mongo_landing_collection=_required("MONGO_LANDING_COLLECTION"),
            mongo_processed_collection=_required("MONGO_PROCESSED_COLLECTION"),
            minio_endpoint=_required("MINIO_ENDPOINT"),
            minio_access_key=_required("MINIO_ACCESS_KEY"),
            minio_secret_key=_required("MINIO_SECRET_KEY"),
            minio_secure=_as_bool("MINIO_SECURE", False),
            minio_landing_bucket=_required("MINIO_LANDING_BUCKET"),
            minio_processed_bucket=_required("MINIO_PROCESSED_BUCKET"),
            scrape_partition_months=int(os.getenv("SCRAPE_PARTITION_MONTHS", "1")),
            scrape_retry_times=int(os.getenv("SCRAPE_RETRY_TIMES", "3")),
            scrape_download_timeout=int(
                os.getenv("SCRAPE_DOWNLOAD_TIMEOUT", "60")
            ),
            scrape_refresh_existing=_as_bool("SCRAPE_REFRESH_EXISTING", False),
            wrc_search_url=os.getenv(
                "WRC_SEARCH_URL",
                "https://www.workplacerelations.ie/en/search/?advance=true",
            ),
            wrc_user_agent=os.getenv(
                "WRC_USER_AGENT", "kedra-wrc-assessment/1.0"
            ),
        )
