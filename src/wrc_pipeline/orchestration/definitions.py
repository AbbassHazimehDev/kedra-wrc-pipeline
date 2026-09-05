"""Dagster job that runs the existing ingestion and transformation commands."""

import subprocess
import sys
from pathlib import Path

from dagster import Definitions, In, Nothing, Out, job, op


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@op(
    config_schema={"start_date": str, "end_date": str},
    out=Out(Nothing),
)
def ingestion_op(context) -> None:
    """Run the normal Scrapy ingestion command for the configured range."""
    config = context.op_config
    subprocess.run(
        [
            sys.executable,
            "-m",
            "scrapy",
            "crawl",
            "decisions",
            "-a",
            f"start_date={config['start_date']}",
            "-a",
            f"end_date={config['end_date']}",
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


@op(config_schema={"start_date": str, "end_date": str}, ins={"ingestion": In(Nothing)})
def transformation_op(context, ingestion) -> None:
    """Run transformation only after ingestion completes successfully."""
    del ingestion
    config = context.op_config
    subprocess.run(
        [
            sys.executable,
            "-m",
            "wrc_pipeline.transformation.transform",
            "--start-date",
            config["start_date"],
            "--end-date",
            config["end_date"],
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


@job
def wrc_pipeline_job():
    """Define the ingestion -> transformation dependency."""
    transformation_op(ingestion_op())


defs = Definitions(jobs=[wrc_pipeline_job])
