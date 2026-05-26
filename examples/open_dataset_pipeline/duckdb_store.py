from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

import duckdb

from open_dataset_pipeline.pipeline import OpenDatasetRequest


def _dataset_slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "dataset"


def _table_name(dataset_name: str) -> str:
    return f"{_dataset_slug(dataset_name).replace('-', '_')}_rows"


class OpenDatasetLoader:
    def load_bytes(self, source_url: str) -> bytes:
        parsed = urlparse(source_url)
        if parsed.scheme in {"http", "https"}:
            with urlopen(source_url, timeout=30) as response:  # noqa: S310
                return response.read()
        if parsed.scheme == "file":
            path = Path(unquote(parsed.path))
            return path.read_bytes()
        return Path(source_url).read_bytes()


class DuckDBOpenDatasetStore:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)

    def persist(
        self, request: OpenDatasetRequest, raw_bytes: bytes
    ) -> dict[str, object]:
        dataset_slug = _dataset_slug(request.dataset_name)
        dated_root = Path(dataset_slug) / f"dt={request.export_date}"
        raw_key = Path("raw") / dated_root / f"{request.run_id}.csv"
        duckdb_key = Path("duckdb") / dated_root / f"{request.run_id}.duckdb"
        manifest_key = Path("manifests") / dated_root / f"{request.run_id}.json"

        raw_path = self.output_dir / raw_key
        duckdb_path = self.output_dir / duckdb_key
        manifest_path = self.output_dir / manifest_key

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        raw_path.write_bytes(raw_bytes)

        table_name = _table_name(request.dataset_name)
        connection = duckdb.connect(str(duckdb_path))
        try:
            connection.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                "SELECT * FROM read_csv_auto(?, HEADER=TRUE)",
                [str(raw_path)],
            )
            row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            if row is None:
                raise RuntimeError("duckdb count query returned no rows")
            row_count = row[0]
        finally:
            connection.close()

        manifest = {
            "dataset": request.dataset_name,
            "export_date": request.export_date,
            "exported_at": request.exported_at.isoformat(),
            "objects": {
                "raw": str(raw_key),
                "duckdb": str(duckdb_key),
                "manifest": str(manifest_key),
            },
            "row_count": int(row_count),
            "run_id": request.run_id,
            "source_url": request.source_url,
            "status": "succeeded",
            "table_name": table_name,
        }
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        return manifest
