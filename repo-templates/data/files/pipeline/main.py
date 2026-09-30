"""__PIPELINE_NAME__ Spark job: extract, transform, check, then load."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from pipeline import checks as quality

PIPELINE = "__PIPELINE_NAME__"

EXIT_OK = 0
EXIT_CHECKS_FAILED = 1
EXIT_BAD_INPUT = 2


def emit(event: str, **fields: object) -> None:
    payload = {
        "pipeline": PIPELINE,
        "event": event,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        **fields,
    }
    print(json.dumps(payload, default=str), flush=True)


def extract(spark: SparkSession, source: str) -> DataFrame:
    """Read source data without modifying it."""
    emit("extract_started", source=source)
    frame = spark.read.parquet(source)
    emit("extract_completed", source=source, rows=frame.count())
    return frame


def transform(frame: DataFrame) -> DataFrame:
    """Shape the data. Replace this with the real transformation."""
    emit("transform_started")
    result = frame.withColumn("ingested_at", F.current_timestamp())
    emit("transform_completed", rows=result.count())
    return result


def load(frame: DataFrame, target: str, partition_by: list[str]) -> None:
    """Publish only after checks pass; refuse to overwrite an existing target."""
    emit("load_started", target=target)
    writer = frame.write.mode("errorifexists").format("parquet")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.save(target)
    emit("load_completed", target=target)


def write_report(path: str, body: str) -> None:
    """Write one report object, not Spark part files. EMR supplies boto3."""
    if path.startswith("s3://"):
        import boto3

        bucket, _, key = path.removeprefix("s3://").partition("/")
        boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=body.encode())
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{PIPELINE} pipeline")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--checks", required=True, help="Path to checks.json.")
    parser.add_argument("--report", required=True, help="Where to write the check report.")
    parser.add_argument("--source", required=True, help="Input location.")
    parser.add_argument("--target", required=True, help="Curated output location.")
    parser.add_argument("--partition-by", default="", help="Comma-separated partition columns.")
    parser.add_argument("--dry-run", action="store_true", help="Run every stage except load.")
    args = parser.parse_args(argv)

    spark = SparkSession.builder.appName(f"{PIPELINE}-{args.run_id}").getOrCreate()
    emit("run_started", run_id=args.run_id, dry_run=args.dry_run)

    try:
        declared = quality.load_checks(args.checks)
    except quality.CheckDefinitionError as error:
        # The checks are wrong, which is a different problem from bad data.
        emit("run_failed", reason="invalid_checks", error=str(error))
        return EXIT_BAD_INPUT

    try:
        curated = transform(extract(spark, args.source))
    except Exception as error:  # noqa: BLE001 - the job boundary logs and exits
        emit(
            "run_failed",
            reason="transform_error",
            error=str(error),
            error_type=type(error).__name__,
        )
        return EXIT_CHECKS_FAILED

    results = quality.run_checks(declared, {"curated": curated})
    write_report(args.report, quality.report(results, args.run_id))

    for result in results:
        emit(
            "check_evaluated",
            check=result.name,
            status=result.status,
            observed=result.observed,
            threshold=result.threshold,
            blocking=result.blocking,
            detail=result.detail,
        )

    if quality.should_stop(results):
        emit("run_failed", reason="checks_blocked_load", report=args.report)
        return EXIT_CHECKS_FAILED

    if args.dry_run:
        emit("run_succeeded", loaded=False, reason="dry_run")
        return EXIT_OK

    partitions = [column for column in args.partition_by.split(",") if column]
    load(curated, args.target, partitions)
    emit("run_succeeded", loaded=True, report=args.report)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
