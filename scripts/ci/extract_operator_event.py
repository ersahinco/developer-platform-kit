#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _event_from_message(
    message: str, *, event_names: set[str]
) -> dict[str, Any] | None:
    try:
        parsed = json.loads(message)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    if parsed.get("event") not in event_names:
        return None
    return parsed


def extract_event(
    document: dict[str, Any],
    *,
    event_names: set[str],
    run_id: str | None,
) -> dict[str, Any]:
    matches: list[tuple[int, dict[str, Any]]] = []
    for raw_event in document.get("events", []):
        if not isinstance(raw_event, dict):
            continue
        message = raw_event.get("message")
        if not isinstance(message, str):
            continue
        parsed = _event_from_message(message, event_names=event_names)
        if parsed is None:
            continue
        if run_id is not None and parsed.get("run_id") != run_id:
            continue
        timestamp = raw_event.get("timestamp")
        matches.append((timestamp if isinstance(timestamp, int) else 0, parsed))

    if not matches:
        run_filter = f" for run_id {run_id!r}" if run_id else ""
        expected = ", ".join(sorted(event_names))
        raise ValueError(f"no operator event found for {expected}{run_filter}")

    return max(matches, key=lambda item: item[0])[1]


def render_operational_snapshot_summary(event: dict[str, Any]) -> str:
    return "\n".join(
        [
            "### Operational snapshot",
            "",
            f"- Run ID: `{event.get('run_id', 'unknown')}`",
            f"- Status: {event.get('status', 'unknown')}",
            f"- READ_MODE: {event.get('read_mode', 'unknown')}",
            f"- WRITE_MODE: {event.get('write_mode', 'unknown')}",
            f"- Customers: {event.get('customers_count', 'unknown')}",
            f"- Orders: {event.get('orders_count', 'unknown')}",
            f"- Order contact emails: {event.get('order_contact_email_count', 'unknown')}",
            f"- Pending outbox rows: {event.get('outbox_pending_count', 'unknown')}",
            f"- Event receipts: {event.get('event_receipts_count', 'unknown')}",
        ]
    )


def render_backfill_summary(event: dict[str, Any]) -> str:
    lines = [
        "### Data backfill event",
        "",
        f"- Event: {event.get('event', 'unknown')}",
        f"- Job: {event.get('job_name', 'unknown')}",
        f"- Message: {event.get('message', 'unknown')}",
    ]
    for key, label in [
        ("last_order_id", "Last order ID"),
        ("rows_processed", "Rows processed"),
        ("batches_processed", "Batches processed"),
        ("inserted", "Inserted rows"),
        ("elapsed_ms", "Elapsed ms"),
    ]:
        if key in event:
            lines.append(f"- {label}: {event[key]}")
    return "\n".join(lines)


def render_summary(event: dict[str, Any], *, summary_type: str) -> str:
    if summary_type == "operational-snapshot":
        return render_operational_snapshot_summary(event)
    if summary_type == "backfill":
        return render_backfill_summary(event)
    raise ValueError(f"unsupported summary type {summary_type!r}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract the latest structured operator event from CloudWatch Logs output."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--event-name",
        action="append",
        required=True,
        help="Structured event name to match. Repeat to accept multiple terminal events.",
    )
    parser.add_argument("--run-id")
    parser.add_argument(
        "--summary",
        choices=["operational-snapshot", "backfill"],
    )
    args = parser.parse_args()

    document = json.loads(args.path.read_text(encoding="utf-8"))
    event = extract_event(
        document,
        event_names=set(args.event_name),
        run_id=args.run_id,
    )
    if args.summary:
        print(render_summary(event, summary_type=args.summary))
    else:
        print(json.dumps(event, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
