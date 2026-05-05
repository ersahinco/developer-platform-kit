import datetime
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol

DATASET_ORDER_CONTACT_EMAIL = "order_contact_email"
SOURCE_QUERY_ORDER_CONTACT_EMAIL = "order_contact_email_v1"
ORDER_CONTACT_EMAIL_FIELDS = ["order_id", "billing_email", "source", "updated_at"]


@dataclass(frozen=True)
class DataExportRequest:
    export_date: str
    run_id: str
    exported_at: datetime.datetime


@dataclass(frozen=True)
class ExportedObject:
    key: str
    byte_count: int
    sha256: str | None = None
    row_count: int | None = None
    local_path: str | None = None


class OrderContactEmailExportReader(Protocol):
    def rows(self) -> Iterable[Mapping[str, Any]]: ...


class DataExportStore(Protocol):
    def write_csv(
        self,
        *,
        key: str,
        fieldnames: list[str],
        rows: Iterable[Mapping[str, Any]],
    ) -> ExportedObject: ...

    def write_json(self, *, key: str, payload: Mapping[str, Any]) -> ExportedObject: ...


class DataExportPublisher(Protocol):
    def publish(self, objects: list[ExportedObject]) -> None: ...


def order_contact_email_keys(request: DataExportRequest) -> tuple[str, str]:
    prefix = f"{DATASET_ORDER_CONTACT_EMAIL}/dt={request.export_date}/{request.run_id}"
    return f"raw/{prefix}.csv", f"manifests/{prefix}.json"


def build_success_manifest(
    *,
    request: DataExportRequest,
    raw: ExportedObject,
    manifest_key: str,
    row_count: int,
) -> dict[str, Any]:
    return {
        "dataset": DATASET_ORDER_CONTACT_EMAIL,
        "source_query": SOURCE_QUERY_ORDER_CONTACT_EMAIL,
        "run_id": request.run_id,
        "export_date": request.export_date,
        "exported_at": request.exported_at.isoformat(),
        "status": "succeeded",
        "row_count": row_count,
        "raw_byte_count": raw.byte_count,
        "raw_sha256": raw.sha256,
        "objects": {
            "raw": raw.key,
            "manifest": manifest_key,
        },
    }


def validate_success_manifest(
    *,
    raw: ExportedObject,
    manifest: Mapping[str, Any],
) -> None:
    if manifest.get("status") != "succeeded":
        raise ValueError("manifest status must be succeeded")

    row_count = manifest.get("row_count")
    if not isinstance(row_count, int) or row_count < 0:
        raise ValueError("manifest row_count must be a non-negative integer")

    objects = manifest.get("objects")
    if not isinstance(objects, Mapping) or objects.get("raw") != raw.key:
        raise ValueError("manifest objects.raw must match the raw export key")

    if manifest.get("raw_byte_count") != raw.byte_count:
        raise ValueError(
            "manifest raw_byte_count mismatch: "
            f"expected {manifest.get('raw_byte_count')}, got {raw.byte_count}"
        )

    if manifest.get("raw_sha256") != raw.sha256:
        raise ValueError("manifest raw_sha256 mismatch")


def run_order_contact_email_export(
    *,
    request: DataExportRequest,
    reader: OrderContactEmailExportReader,
    store: DataExportStore,
    publisher: DataExportPublisher | None = None,
) -> dict[str, Any]:
    raw_key, manifest_key = order_contact_email_keys(request)
    raw = store.write_csv(
        key=raw_key,
        fieldnames=ORDER_CONTACT_EMAIL_FIELDS,
        rows=reader.rows(),
    )
    manifest = build_success_manifest(
        request=request,
        raw=raw,
        manifest_key=manifest_key,
        row_count=raw.row_count or 0,
    )
    validate_success_manifest(raw=raw, manifest=manifest)
    manifest_object = store.write_json(key=manifest_key, payload=manifest)

    if publisher is not None:
        publisher.publish([raw, manifest_object])

    return manifest
