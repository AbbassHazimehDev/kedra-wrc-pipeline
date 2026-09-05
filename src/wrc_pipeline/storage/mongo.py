"""MongoDB metadata storage for landing and processed documents."""

from datetime import date, datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection

from wrc_pipeline.config import AppConfig


class MongoStorage:
    """Own a MongoDB client and expose the configured metadata collections."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.from_env()
        self.client = MongoClient(self.config.mongo_uri)
        self.database = self.client[self.config.mongo_database]
        self.landing_documents: Collection[dict[str, Any]] = self.database[
            self.config.mongo_landing_collection
        ]
        self.processed_documents: Collection[dict[str, Any]] = self.database[
            self.config.mongo_processed_collection
        ]

    def ensure_indexes(self) -> None:
        """Create indexes needed for range queries and idempotent writes."""
        self.landing_documents.create_index(
            [("source_identity", ASCENDING), ("file_hash", ASCENDING)],
            unique=True,
            name="landing_source_identity_file_hash",
        )
        self.landing_documents.create_index(
            [("source_identity", ASCENDING), ("ingested_at", DESCENDING)],
            name="landing_latest_by_source",
        )
        self.landing_documents.create_index(
            [("published_date", ASCENDING)], name="landing_published_date"
        )
        self.processed_documents.create_index(
            [("transformation_identity", ASCENDING)],
            unique=True,
            name="processed_transformation_identity",
        )

    def find_latest_landing(
        self, source_identity: str
    ) -> dict[str, Any] | None:
        """Return the newest landing version for a source identity."""
        return self.landing_documents.find_one(
            {"source_identity": source_identity},
            sort=[("ingested_at", DESCENDING)],
        )

    def find_landing_by_range(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Return landing metadata whose published date is in an inclusive range."""
        return list(
            self.landing_documents.find(
                {
                    "published_date": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat(),
                    }
                }
            ).sort("published_date", ASCENDING)
        )

    @staticmethod
    def now() -> datetime:
        """Return a timezone-aware UTC timestamp for metadata."""
        return datetime.now(timezone.utc)

    def close(self) -> None:
        """Close the underlying MongoDB client."""
        self.client.close()
