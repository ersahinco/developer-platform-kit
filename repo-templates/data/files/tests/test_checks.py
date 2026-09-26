"""Check-engine tests.

These run without Spark. The engine only needs count, filter, select, distinct
and columns, so a small fake stands in for a DataFrame and the tests stay fast
enough to run on every commit.
"""

from __future__ import annotations

import json

import pytest

from pipeline import checks as quality


class FakeFrame:
    """Enough of the DataFrame surface for the checks, with scripted counts."""

    def __init__(
        self,
        columns: list[str],
        rows: int,
        filtered: dict[str, int] | None = None,
        distinct_count: int | None = None,
    ) -> None:
        self._columns = columns
        self._rows = rows
        self._filtered = filtered or {}
        self._distinct = distinct_count if distinct_count is not None else rows
        self._selected = False

    @property
    def columns(self) -> list[str]:
        return self._columns

    def count(self) -> int:
        return self._rows

    def filter(self, condition: str) -> FakeFrame:
        return FakeFrame(self._columns, self._filtered.get(condition, 0))

    def select(self, *columns: str) -> FakeFrame:
        frame = FakeFrame(list(columns), self._rows, distinct_count=self._distinct)
        frame._selected = True
        return frame

    def distinct(self) -> FakeFrame:
        return FakeFrame(self._columns, self._distinct)


def test_row_count_min_passes_and_fails() -> None:
    check = {"name": "rows", "dataset": "curated", "kind": "row_count_min", "value": 10}
    assert quality.evaluate(check, FakeFrame(["id"], 10)).status == "passed"
    assert quality.evaluate(check, FakeFrame(["id"], 9)).status == "failed"


def test_unique_compares_distinct_to_total() -> None:
    check = {"name": "unique-id", "dataset": "curated", "kind": "unique", "column": "id"}
    assert quality.evaluate(check, FakeFrame(["id"], 100, distinct_count=100)).status == "passed"
    assert quality.evaluate(check, FakeFrame(["id"], 100, distinct_count=98)).status == "failed"


def test_null_rate_uses_the_threshold() -> None:
    check = {
        "name": "nulls",
        "dataset": "curated",
        "kind": "null_rate_max",
        "column": "id",
        "value": 0.01,
    }
    frame = FakeFrame(["id"], 1000, filtered={"id IS NULL": 5})
    assert quality.evaluate(check, frame).status == "passed"
    frame = FakeFrame(["id"], 1000, filtered={"id IS NULL": 50})
    assert quality.evaluate(check, frame).status == "failed"


def test_missing_column_errors_rather_than_fails() -> None:
    """An absent column is a broken check, not bad data. Different fix."""
    check = {
        "name": "nulls",
        "dataset": "curated",
        "kind": "null_rate_max",
        "column": "absent",
        "value": 0,
    }
    result = quality.evaluate(check, FakeFrame(["id"], 10))
    assert result.status == "errored"
    assert "absent" in result.detail


def test_empty_dataset_errors_on_a_rate_check() -> None:
    check = {
        "name": "nulls",
        "dataset": "curated",
        "kind": "null_rate_max",
        "column": "id",
        "value": 0,
    }
    result = quality.evaluate(check, FakeFrame(["id"], 0))
    assert result.status == "errored"


def test_missing_dataset_errors_and_names_it() -> None:
    checks = [{"name": "rows", "dataset": "staging", "kind": "row_count_min", "value": 1}]
    results = quality.run_checks(checks, {"curated": FakeFrame(["id"], 5)})
    assert results[0].status == "errored"
    assert "staging" in results[0].detail


def _result(status: str, blocking: bool) -> quality.CheckResult:
    return quality.CheckResult(
        name="rows",
        dataset="curated",
        kind="row_count_min",
        status=status,
        observed="0",
        threshold=">= 1",
        blocking=blocking,
    )


def test_warnings_do_not_stop_the_run() -> None:
    assert quality.should_stop([_result("failed", blocking=False)]) is False


def test_blocking_failure_and_error_both_stop_the_run() -> None:
    assert quality.should_stop([_result("failed", blocking=True)]) is True
    # An error stops the run whether or not the check was blocking: a check that
    # could not run has proved nothing either way.
    assert quality.should_stop([_result("errored", blocking=False)]) is True


def test_unknown_kind_is_rejected_before_any_data_is_read(tmp_path) -> None:
    path = tmp_path / "checks.json"
    path.write_text(json.dumps({"checks": [{"name": "x", "dataset": "curated", "kind": "vibes"}]}))
    with pytest.raises(quality.CheckDefinitionError, match="unknown kind"):
        quality.load_checks(str(path))


def test_empty_check_file_is_rejected(tmp_path) -> None:
    path = tmp_path / "checks.json"
    path.write_text('{"checks": []}')
    with pytest.raises(quality.CheckDefinitionError, match="no checks"):
        quality.load_checks(str(path))


def test_runtime_exception_is_reported_and_blocks_even_a_warning() -> None:
    check = {
        "name": "rows",
        "dataset": "curated",
        "kind": "row_count_min",
        "value": "invalid",
        "blocking": False,
    }
    results = quality.run_checks([check], {"curated": FakeFrame(["id"], 3)})
    assert results[0].status == "errored"
    assert "ValueError" in results[0].detail
    assert quality.should_stop(results)


def test_invalid_json_has_a_definition_error(tmp_path) -> None:
    path = tmp_path / "checks.json"
    path.write_text("{")
    with pytest.raises(quality.CheckDefinitionError, match="Cannot load"):
        quality.load_checks(str(path))
