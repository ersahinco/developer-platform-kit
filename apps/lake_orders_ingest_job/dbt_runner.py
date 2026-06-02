from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from dataclasses import dataclass

import duckdb


class DbtBuildFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class TransformResult:
    warehouse_path: Path
    transform_tool: str
    transform_execution: str


class DbtDuckDBRunner:
    def __init__(self, *, project_dir: Path) -> None:
        self._project_dir = project_dir

    def build(
        self,
        *,
        run_dir: Path,
        warehouse_path: Path,
        raw_parquet_path: Path,
        ingest_date: str,
    ) -> TransformResult:
        run_dir.mkdir(parents=True, exist_ok=True)
        try:
            warehouse = self._build_with_dbt(
                run_dir=run_dir,
                warehouse_path=warehouse_path,
                raw_parquet_path=raw_parquet_path,
                ingest_date=ingest_date,
            )
            return TransformResult(
                warehouse_path=warehouse,
                transform_tool="dbt-duckdb",
                transform_execution="dbt_cli",
            )
        except Exception as exc:  # noqa: BLE001
            try:
                warehouse = self._build_model_sql_with_duckdb(
                    warehouse_path=warehouse_path,
                    raw_parquet_path=raw_parquet_path,
                    ingest_date=ingest_date,
                )
                return TransformResult(
                    warehouse_path=warehouse,
                    transform_tool="dbt-duckdb",
                    transform_execution="duckdb_sql_fallback",
                )
            except Exception as fallback_exc:  # noqa: BLE001
                raise DbtBuildFailed(
                    "dbt build failed and DuckDB model fallback also failed\n"
                    f"dbt error:\n{exc}\n"
                    f"fallback error:\n{fallback_exc}"
                ) from fallback_exc

    def _build_with_dbt(
        self,
        *,
        run_dir: Path,
        warehouse_path: Path,
        raw_parquet_path: Path,
        ingest_date: str,
    ) -> Path:
        profiles_dir = run_dir / "dbt_profiles"
        target_dir = run_dir / "dbt_target"
        logs_dir = run_dir / "dbt_logs"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        target_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)
        warehouse_path.parent.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "profiles.yml").write_text(
            "\n".join(
                [
                    "lake_orders_ingest:",
                    "  target: local",
                    "  outputs:",
                    "    local:",
                    "      type: duckdb",
                    f"      path: {json.dumps(str(warehouse_path))}",
                    "      threads: 1",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        command = [
            sys.executable,
            "-m",
            "dbt.cli.main",
            "build",
            "--project-dir",
            str(self._project_dir),
            "--profiles-dir",
            str(profiles_dir),
            "--target-path",
            str(target_dir),
            "--vars",
            json.dumps(
                {
                    "raw_parquet_path": str(raw_parquet_path),
                    "ingest_date": ingest_date,
                },
                sort_keys=True,
            ),
        ]
        result = subprocess.run(
            command,
            cwd=run_dir,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise DbtBuildFailed(
                f"dbt build failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return warehouse_path

    def _build_model_sql_with_duckdb(
        self,
        *,
        warehouse_path: Path,
        raw_parquet_path: Path,
        ingest_date: str,
    ) -> Path:
        model_path = self._project_dir / "models" / "curated_lake_orders.sql"
        model_sql = model_path.read_text(encoding="utf-8")
        compiled_sql = model_sql.replace(
            '{{ var("raw_parquet_path") }}',
            _sql_string_value(str(raw_parquet_path)),
        ).replace(
            '{{ var("ingest_date") }}',
            _sql_string_value(ingest_date),
        )
        warehouse_path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(warehouse_path))
        try:
            connection.execute(
                f"CREATE OR REPLACE TABLE curated_lake_orders AS {compiled_sql}"
            )
            _assert_model_tests(connection)
        finally:
            connection.close()
        return warehouse_path


def _sql_string_value(value: str) -> str:
    return value.replace("'", "''")


def _assert_model_tests(connection: duckdb.DuckDBPyConnection) -> None:
    duplicate = connection.execute(
        """
        SELECT order_id
        FROM curated_lake_orders
        GROUP BY order_id
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    ).fetchone()
    if duplicate is not None:
        raise ValueError(f"curated_lake_orders order_id is not unique: {duplicate[0]}")

    nulls = connection.execute(
        """
        SELECT COUNT(*)
        FROM curated_lake_orders
        WHERE order_id IS NULL
           OR customer_id IS NULL
           OR customer_order_sequence IS NULL
        """
    ).fetchone()
    if nulls is None or int(nulls[0]) != 0:
        raise ValueError("curated_lake_orders failed not-null model checks")
