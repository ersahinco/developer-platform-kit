"""Runtime logging settings and structured fields."""

import json
import logging

from app.logging_setup import configure_logging


def test_logging_uses_environment_and_preserves_extra_fields(monkeypatch, capsys):
    monkeypatch.setenv("WORKLOAD_NAME", "payments")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", root.level)
    configure_logging()
    root.debug("processed %s", "order", extra={"order_id": 42})
    record = json.loads(capsys.readouterr().out)
    assert record["workload"] == "payments"
    assert record["environment"] == "test"
    assert record["level"] == "DEBUG"
    assert record["message"] == "processed order"
    assert record["order_id"] == 42
    assert "args" not in record
