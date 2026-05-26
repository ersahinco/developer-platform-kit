from __future__ import annotations

from dataclasses import dataclass
import datetime
from typing import Protocol


@dataclass(frozen=True)
class OpenDatasetRequest:
    dataset_name: str
    source_url: str
    export_date: str
    run_id: str
    exported_at: datetime.datetime


class DatasetLoader(Protocol):
    def load_bytes(self, source_url: str) -> bytes: ...


class DatasetStore(Protocol):
    def persist(
        self, request: OpenDatasetRequest, raw_bytes: bytes
    ) -> dict[str, object]: ...


def run_open_dataset_pipeline(
    request: OpenDatasetRequest,
    loader: DatasetLoader,
    store: DatasetStore,
) -> dict[str, object]:
    raw_bytes = loader.load_bytes(request.source_url)
    return store.persist(request, raw_bytes)
