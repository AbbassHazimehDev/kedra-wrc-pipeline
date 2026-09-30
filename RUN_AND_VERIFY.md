# Kedra WRC Pipeline: Local Run and Count Verification

This runbook is for running one date range from the Dagster UI and checking how many documents were ingested and transformed.

The commands below are written for Windows PowerShell.

## 1. Open the project

```powershell
Set-Location C:\Users\Hp\Downloads\kedra-wrc-pipeline
```

Choose the date range once. Use the same dates in both Dagster operations.
The current spider searches all four WRC bodies for every selected partition.

```powershell
$StartDate = "2024-02-01"
$EndDate = "2024-02-29"
$Partition = "2024-02"
```

For another month, change all three values. For example:

```powershell
$StartDate = "2024-03-01"
$EndDate = "2024-03-31"
$Partition = "2024-03"
```

## Date-range configuration examples

These configurations are supported by the current Dagster job. In every example,
the same date range is used for ingestion and transformation.

### Example A: one day

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

This is useful for a small interview demonstration.

### Example B: one month

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"

  transformation_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
```

This searches all four WRC bodies for February 2024.

### Example C: three months

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-01-01"
      end_date: "2024-03-31"

  transformation_op:
    config:
      start_date: "2024-01-01"
      end_date: "2024-03-31"
```

With SCRAPE_PARTITION_MONTHS=1, this creates three monthly partitions:

```text
2024-01
2024-02
2024-03
```

### Body-filter configuration: important current limitation

The current code does not yet support selecting only specific bodies from the
Dagster UI. The current configuration schema accepts only start_date and
end_date, and the spider intentionally loops through all four configured WRC
bodies.

Therefore, do not paste the following examples into the current Dagster UI yet:

Example D: Workplace Relations Commission only

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Workplace Relations Commission

  transformation_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Workplace Relations Commission
```

Example E: Labour Court only

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Labour Court

  transformation_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Labour Court
```

Example F: Equality Tribunal only

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Equality Tribunal

  transformation_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Equality Tribunal
```

Example G: Employment Appeals Tribunal only

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Employment Appeals Tribunal

  transformation_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Employment Appeals Tribunal
```

Example H: two selected bodies

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Workplace Relations Commission
        - Labour Court

  transformation_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
      bodies:
        - Workplace Relations Commission
        - Labour Court
```

This is the intended configuration shape if body filtering is added later.
The implementation would need to add bodies to the Dagster config schema,
pass it to the Scrapy command, validate the names against the WRC body mapping,
and apply the same selection during transformation.

The WRC body mapping currently used by the spider is:

```text
Employment Appeals Tribunal       -> 2
Equality Tribunal                 -> 1
Labour Court                      -> 3
Workplace Relations Commission    -> 15376
```

For the interview, explain that all bodies are currently scraped because the
assessment asks for every body, while a runtime body filter would be passed
through Dagster configuration after adding that option to the implementation.

## 2. Prepare Python and environment variables

Run this once after cloning the project, or whenever dependencies change:

```powershell
uv sync
```

Create the local `.env` file if it does not exist:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

Never commit `.env`. It contains local configuration and credentials.

## 3. Start MongoDB and MinIO

Make sure Docker Desktop is running, then execute:

```powershell
docker compose up -d
docker compose ps
```

Both containers should be running and healthy:

```text
kedra-wrc-mongodb
kedra-wrc-minio
```

Verify MongoDB:

```powershell
docker exec kedra-wrc-mongodb mongosh --quiet --eval "db.adminCommand({ ping: 1 })"
```

Expected result:

```text
{ ok: 1 }
```

Verify MinIO:

```powershell
curl.exe -fsS -o NUL -w "minio_health_http=%{http_code}`n" http://localhost:9000/minio/health/live
```

Expected result:

```text
minio_health_http=200
```

## 4. Start Dagster

Run this in a dedicated terminal and keep it open:

```powershell
$env:PYTHONLEGACYWINDOWSSTDIO = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
uv run dagster dev -m wrc_pipeline.orchestration.definitions
```

Open the Dagster UI:

```text
http://localhost:3000
```

The `PYTHONLEGACYWINDOWSSTDIO` setting allows Dagster to capture the subprocess stdout and display the JSON pipeline logs in the UI. If the UI says `No log file available`, stop Dagster with `Ctrl+C` and restart it with this setting.

## 5. Launch the run in Dagster UI

In Dagster:

1. Open **Jobs**.
2. Open `wrc_pipeline_job`.
3. Click **Launch Run**.
4. Paste this configuration, using your selected dates:

```yaml
ops:
  ingestion_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"

  transformation_op:
    config:
      start_date: "2024-02-01"
      end_date: "2024-02-29"
```

5. Click **Launch Run**.
6. Wait until both `ingestion_op` and `transformation_op` are green.

Dagster executes the operations in this order:

```text
ingestion_op -> transformation_op
```

Transformation starts only after ingestion finishes successfully.

## 6. Read the ingestion result

Open the completed run and select `ingestion_op`.

Find the final JSON event named `run_summary`:

```json
{
  "event": "run_summary",
  "expected_results": 350,
  "records_found": 350,
  "records_succeeded": 350,
  "records_failed": 0,
  "records_skipped": 0
}
```

Interpret the fields as follows:

| Field | Meaning |
| --- | --- |
| `expected_results` | Result rows reported by the website |
| `records_found` | Search result rows parsed by the spider |
| `records_succeeded` | New records successfully stored in the Landing Zone |
| `records_failed` | Records that failed, including the logged reason and URL |
| `records_skipped` | Existing unchanged records skipped before downloading |

For a clean first run, the main ingestion number is `records_succeeded`.

## 7. Read the transformation result

Select `transformation_op` and find the final `transformation_summary` event:

```json
{
  "event": "transformation_summary",
  "found": 350,
  "succeeded": 350,
  "skipped": 0,
  "failed": 0
}
```

Interpret the fields as follows:

| Field | Meaning |
| --- | --- |
| `found` | Landing metadata records selected for transformation |
| `succeeded` | New records written to the Processed Zone |
| `skipped` | Records already transformed with the same content |
| `failed` | Transformation failures |

For a clean first run, the main transformation number is `succeeded`.

## 8. Verify the total stored documents in MongoDB

The following command checks the total Landing and Processed metadata for the selected partition:

```powershell
docker exec kedra-wrc-mongodb mongosh --quiet --eval "const d=db.getSiblingDB('wrc_pipeline'); const q={partition_date:'$Partition'}; printjson({landing_metadata:d.raw_documents.countDocuments(q), processed_metadata:d.processed_documents.countDocuments(q)})"
```

Example result:

```json
{
  "landing_metadata": 350,
  "processed_metadata": 350
}
```

MongoDB stores metadata. Each metadata record points to the corresponding file in MinIO.

## 9. Verify the total stored files in MinIO

This command counts the files for the selected partition in both MinIO buckets. It reads MinIO connection settings from `.env` through the project configuration.

```powershell
@"
from minio import Minio
from wrc_pipeline.config import AppConfig

config = AppConfig.from_env()
client = Minio(
    config.minio_endpoint,
    access_key=config.minio_access_key,
    secret_key=config.minio_secret_key,
    secure=config.minio_secure,
)

month = "$Partition"

for bucket, prefix in (
    (config.minio_landing_bucket, config.minio_landing_prefix),
    (config.minio_processed_bucket, config.minio_processed_prefix),
):
    count = sum(
        1
        for obj in client.list_objects(
            bucket,
            prefix=f"{prefix}/",
            recursive=True,
        )
        if f"/{month}/" in obj.object_name
    )
    print(f"{bucket}: {count} objects")
"@ | uv run python -
```

Example result:

```text
wrc-landing: 350 objects
wrc-processed: 350 objects
```

You can also open the MinIO console at:

```text
http://localhost:9001
```

Then open the `wrc-landing` and `wrc-processed` buckets to inspect the actual files.

## 10. The simple interview explanation

Say:

> I launched one Dagster run for the selected month. Dagster first ran ingestion, which searched the website and stored the original files and metadata in the Landing Zone. After ingestion succeeded, Dagster ran transformation, which read the Landing Zone, cleaned HTML files, copied PDF/DOC files unchanged, and stored the results in the Processed Zone. I verified the run summaries in Dagster and then checked the Landing and Processed counts in MongoDB and MinIO.

## 11. How to interpret a rerun

If you run the same month again without refreshing, this is expected:

```text
records_succeeded: 0
records_skipped: N
```

That means existing unchanged records were detected and not downloaded again.

For transformation, this is expected on a rerun:

```text
succeeded: 0
skipped: N
```

That means the Processed files already exist with the same transformed hash.

Do not treat `records_found` as the final unique-document count. It counts search result rows, and a website can expose duplicate rows. Use the MongoDB and MinIO counts for the actual stored totals, and always report failures separately.
