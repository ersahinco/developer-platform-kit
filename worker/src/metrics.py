import json
import sys


def log_batch(last_order_id: int, inserted: int, elapsed_ms: float) -> None:
    """Emit a structured JSON log line for a completed backfill batch."""
    print(
        json.dumps(
            {
                "last_order_id": last_order_id,
                "inserted": inserted,
                "elapsed_ms": elapsed_ms,
            }
        ),
        file=sys.stdout,
        flush=True,
    )
