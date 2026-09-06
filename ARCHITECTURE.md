# Architecture

The spider uses one-month partitions because the WRC search page returns a manageable result set and exposes a date filter. Monthly boundaries are easy to reason about, avoid large result pages, and allow a failed month/body to be retried independently. Inputs are inclusive `YYYY-MM-DD` dates.

Scrapy uses four concurrent requests by default, a 0.5 second delay, and AutoThrottle targeting one concurrent request per remote host. These values are configurable and intentionally polite for a public government site. HTTP 408, 429, and common 5xx responses are retried three times with a 60 second timeout.

The 500-1000 document workload is bounded by monthly partitions and Scrapy concurrency rather than loaded into memory at once. MongoDB lookups use indexes, one client is reused per crawl/pipeline, and large file contents stay in MinIO. Each item failure is logged and dropped so the remaining crawl can continue. At 1000x this design would be split into independently retryable Body/partition jobs with multiple workers, bulk metadata writes, managed MongoDB/MinIO, and metrics or a queue; the application contracts would remain the same.

MongoDB stores small metadata records; MinIO stores exact source bytes. A SHA-256 hash is calculated before a landing upload. `(source_identity, file_hash)` is unique in MongoDB, where source identity is a hash of the verified Body and identifier. An unchanged existing hash is a no-op. With `refresh_existing=true`, changed bytes receive a new hash-versioned object and metadata record, so old Landing Zone data is never overwritten or deleted.

Transformation reads Landing metadata by published date, downloads the source object, preserves PDF/DOC/DOCX bytes, and cleans only the HTML decision content area. It writes a separate Processed bucket and collection. Processed records are keyed by source identity plus landing hash, so transformation is rerunnable without changing Landing data.

For 50+ sources, I would keep the shared metadata/storage contracts but add source-specific spiders or adapters, centralized source configuration and scheduling, independent retries, monitoring/metrics, and scalable managed MongoDB/object storage. The current assessment intentionally remains a single small deployment.
