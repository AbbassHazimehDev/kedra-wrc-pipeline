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

From the repository root:

```powershell
uv sync
Copy-Item .env.example .env
```

`.env` contains local-only MinIO credentials and is ignored by Git. Adjust any ports or settings there if needed.

## Start and verify local services

```powershell
docker compose up -d
docker compose ps
docker exec kedra-wrc-mongodb mongosh --quiet --eval "db.adminCommand({ ping: 1 })"
(Invoke-WebRequest http://localhost:9000/minio/health/live).StatusCode
```

MongoDB is exposed on `localhost:27017`. MinIO's S3 API is on `localhost:9000`, and its console is on http://localhost:9001. Sign in with `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` from `.env`.

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
uv run dagster job execute -m wrc_pipeline.orchestration.definitions -j wrc_pipeline_job `
  -c run-config.yaml
```

Example `run-config.yaml`:

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-01-01"
      end_date: "2024-01-31"
  transformation_op:
    config:
      start_date: "2024-01-01"
      end_date: "2024-01-31"
```

The file is for local use only and does not contain secrets.

## Tests and inspection

```powershell
uv run pytest
docker compose config
```

To inspect MinIO, open http://localhost:9001 and browse the configured landing and processed buckets. To inspect MongoDB:

```powershell
docker exec -it kedra-wrc-mongodb mongosh wrc_pipeline
db.landing_documents.countDocuments()
db.processed_documents.countDocuments()
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
- If a port is busy, change the host side of the port mapping in `docker-compose.yml` and update `.env` where applicable.
- If the public site returns transient errors, keep the configured polite delay/AutoThrottle and let Scrapy retry; do not disable robots or bypass access controls.
