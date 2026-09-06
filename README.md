# Kedra WRC Pipeline

This project ingests Ireland's publicly available Workplace Relations decisions. Scrapy searches every Body exposed by the WRC decisions page, MongoDB stores metadata, and MinIO stores the original source files in a Landing Zone. A separate transformation stage cleans HTML decisions and writes a Processed Zone. Dagster provides a small ingestion-to-transformation dependency for scheduled or visible runs.

## Architecture

```text
WRC search -> Scrapy spider -> LandingPipeline -> MongoDB metadata
                                      |         -> MinIO landing bucket
                                      v
                         transformation command -> MinIO processed bucket
                                                 -> MongoDB processed collection
```

The spider uses inclusive ISO CLI dates (`YYYY-MM-DD`) and monthly partitions by default. See [ARCHITECTURE.md](ARCHITECTURE.md) and [docs/site-analysis.md](docs/site-analysis.md) for decisions behind the design and the verified site behavior.

## Prerequisites and setup

Install Python 3.11+ and Docker Desktop with Docker Compose. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if it is not already installed:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify the local tools from PowerShell:

```powershell
python --version
uv --version
docker version
docker compose version
```

If you need to clone the repository first:

```powershell
git clone https://github.com/AbbassHazimehDev/kedra-wrc-pipeline.git
Set-Location kedra-wrc-pipeline
```

From the repository root:

```powershell
uv sync
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

`.env` contains local-only MinIO credentials and is ignored by Git. Adjust any ports or settings there if needed.

## Start and verify local services

```powershell
docker compose up -d
docker compose ps
docker exec kedra-wrc-mongodb mongosh --quiet --eval "db.adminCommand({ ping: 1 })"
curl.exe -fsS -o NUL -w "minio_health_http=%{http_code}`n" http://localhost:9000/minio/health/live
```

Expected health results are MongoDB `{ ok: 1 }` and MinIO `minio_health_http=200`. MongoDB is exposed on `localhost:27017`. MinIO's S3 API is on `localhost:9000`, and its console is on http://localhost:9001. Sign in with `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` from `.env`.

## Run ingestion

```powershell
uv run scrapy crawl decisions `
  -a start_date=2024-01-01 `
  -a end_date=2024-01-31
```

The spider visits all four exposed Bodies, follows every result page, and stores original HTML/PDF/DOC/DOCX bytes. To deliberately re-check existing source records for changed bytes:

```powershell
uv run scrapy crawl decisions -a start_date=2024-01-01 -a end_date=2024-01-31 -a refresh_existing=true
```

Important events are JSON lines on stdout. The final `run_summary` reports expected, found, succeeded, failed, and skipped records.

Request, download, parse, and storage failures are logged with the partition, Body, identifier when available, URL, status code when available, and reason. A failed item is dropped after logging so other records in the crawl can continue.

## Run transformation

```powershell
uv run wrc-transform --start-date 2024-01-01 --end-date 2024-01-31
```

PDF, DOC, and DOCX bytes are copied unchanged. HTML is reduced to the verified `div.content` decision area, with navigation, scripts, headers, footers, forms, and buttons removed. Output basenames are `identifier.ext`; body, partition, and source-hash directories prevent collisions. Landing data is never changed or deleted.

## Run Dagster

The minimal Dagster job runs the same commands in order. For the UI:

```powershell
uv run dagster dev -m wrc_pipeline.orchestration.definitions
```

For a direct configured execution:

```powershell
Copy-Item run-config.example.yaml run-config.yaml
uv run dagster job execute -m wrc_pipeline.orchestration.definitions -j wrc_pipeline_job `
  -c run-config.yaml
```

The committed `run-config.example.yaml` contains:

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-01-31"
      end_date: "2024-01-31"
  transformation_op:
    config:
      start_date: "2024-01-31"
      end_date: "2024-01-31"
```

The file is for local use only and does not contain secrets.

## Tests and inspection

```powershell
uv run pytest
uv run python -m compileall -q src tests
uv lock --check
docker compose config
uv run scrapy list
uv run dagster definitions validate -m wrc_pipeline.orchestration.definitions
```

To inspect MinIO, open http://localhost:9001 and browse the configured landing and processed buckets. To inspect MongoDB:

```powershell
docker exec -it kedra-wrc-mongodb mongosh wrc_pipeline
db.raw_documents.countDocuments()
db.processed_documents.countDocuments()
```

For direct metadata inspection:

```powershell
docker exec kedra-wrc-mongodb mongosh --quiet wrc_pipeline --eval "printjson(db.raw_documents.findOne({}, {_id: 0, identifier: 1, body: 1, published_date: 1, partition_date: 1, file_path: 1, file_hash: 1, file_extension: 1}))"
docker exec kedra-wrc-mongodb mongosh --quiet wrc_pipeline --eval "printjson(db.processed_documents.findOne({}, {_id: 0, identifier: 1, transformed_file_path: 1, transformed_file_hash: 1}))"
```

The landing collection uses `(source_identity, file_hash)` for idempotency. Re-running an unchanged range skips known records and does not re-upload their bytes. A deliberate refresh stores changed source bytes as a new hash-versioned landing object while preserving the previous version.

## Stop infrastructure

```powershell
docker compose down
```

Named volumes keep data across restarts. To remove local data intentionally, use `docker compose down -v`.

## Troubleshooting

- If a service is unhealthy, inspect `docker compose logs mongodb` or `docker compose logs minio`.
- If Python imports fail, run `uv sync` from the repository root and use `uv run ...`.
- If another MongoDB already owns IPv4 port 27017 on Windows, point `MONGO_URI` at
  `mongodb://[::1]:27017` for Docker Desktop's IPv6 publication, or stop the conflicting local service.
- If a port is busy, change the host side of the port mapping in `docker-compose.yml` and update `.env` where applicable.
- If the public site returns transient errors, keep the configured polite delay/AutoThrottle and let Scrapy retry; do not disable robots or bypass access controls.

## Code map

- `src/wrc_pipeline/config.py`: environment-backed application configuration.
- `src/wrc_pipeline/settings.py`: Scrapy concurrency, delay, retry, AutoThrottle, and encoding settings.
- `src/wrc_pipeline/spiders/decisions.py`: WRC search, pagination, metadata, and source downloads.
- `src/wrc_pipeline/pipelines.py`: raw-byte hashing and Landing writes.
- `src/wrc_pipeline/storage/`: MongoDB and MinIO adapters.
- `src/wrc_pipeline/utils/`: date partitions, filenames, hashes, and JSON events.
- `src/wrc_pipeline/transformation/transform.py`: Processed-zone transformation.
- `src/wrc_pipeline/orchestration/definitions.py`: Dagster ingestion-to-transformation dependency.
- `tests/`: unit tests for parsing, dates, hashing, storage, idempotency, and transformation.
- `docs/site-analysis.md`: confirmed WRC request and HTML behavior.
