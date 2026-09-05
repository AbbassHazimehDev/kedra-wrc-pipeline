"""Scrapy settings tuned for polite, retryable public-site ingestion."""

import os

from dotenv import load_dotenv

load_dotenv()

BOT_NAME = "wrc_pipeline"
SPIDER_MODULES = ["wrc_pipeline.spiders"]
NEWSPIDER_MODULE = "wrc_pipeline.spiders"

ROBOTSTXT_OBEY = os.getenv("WRC_ROBOTSTXT_OBEY", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
CONCURRENT_REQUESTS = int(os.getenv("SCRAPE_CONCURRENT_REQUESTS", "4"))
DOWNLOAD_DELAY = float(os.getenv("SCRAPE_DOWNLOAD_DELAY", "0.5"))
DOWNLOAD_TIMEOUT = int(os.getenv("SCRAPE_DOWNLOAD_TIMEOUT", "60"))

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = float(
    os.getenv("SCRAPE_AUTOTHROTTLE_START_DELAY", "1.0")
)
AUTOTHROTTLE_MAX_DELAY = float(
    os.getenv("SCRAPE_AUTOTHROTTLE_MAX_DELAY", "60.0")
)
AUTOTHROTTLE_TARGET_CONCURRENCY = float(
    os.getenv("SCRAPE_AUTOTHROTTLE_TARGET_CONCURRENCY", "1.0")
)
AUTOTHROTTLE_DEBUG = False

RETRY_ENABLED = True
RETRY_TIMES = int(os.getenv("SCRAPE_RETRY_TIMES", "3"))
RETRY_HTTP_CODES = [408, 429, 500, 502, 503, 504, 522, 524]

DEFAULT_REQUEST_HEADERS = {
    "User-Agent": os.getenv("WRC_USER_AGENT", "kedra-wrc-assessment/1.0"),
}
ITEM_PIPELINES = {"wrc_pipeline.pipelines.LandingPipeline": 300}
FEED_EXPORT_ENCODING = "utf-8"
