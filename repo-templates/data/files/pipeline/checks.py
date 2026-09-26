"""Declarative data quality checks.

Checks are declared in `checks.json` and evaluated here. Keeping them
declarative means a reviewer reads thresholds in a diff rather than reverse
engineering them from Spark code.

Two outcomes that matter and are never collapsed:

- `failed`  the check ran and the data violated it. Fix the data or the threshold.
- `errored` the check could not run: missing column, unreadable dataset. Fix the
            check or the pipeline. The data may be fine.

A blocking `failed` or any `errored` stops the run. A warning records and
continues.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Protocol

CHECK_KINDS = ("row_count_min", "null_rate_max", "unique", "freshness_max_hours", "accepted_values")


class DataFrameLike(Protocol):
    """The slice of the Spark DataFrame API these checks need."""

    def count(self) -> int: ...

    def filter(self, condition: str) -> DataFrameLike: ...

    def select(self, *columns: str) -> DataFrameLike: ...

    def distinct(self) -> DataFrameLike: ...

    @property
    def columns(self) -> list[str]: ...


@dataclass(frozen=True)
class CheckResult:
    name: str
    dataset: str
    kind: str
    status: str  # passed | failed | errored
    observed: str
    threshold: str
    blocking: bool
    detail: str = ""


class CheckDefinitionError(Exception):
    """The check itself is wrong, before any data was read."""


def load_checks(path: str) -> list[dict[str, Any]]:
    try:
        with open(path) as handle:
            document = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise CheckDefinitionError(f"Cannot load {path}: {error}") from error

    if not isinstance(document, dict):
        raise CheckDefinitionError(f"{path} must contain a checks mapping.")
    checks = document.get("checks")
    if not isinstance(checks, list) or not checks:
        raise CheckDefinitionError(
            f"{path} declares no checks. An empty check file proves nothing."
        )

    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise CheckDefinitionError(f"Check {index} must be a mapping.")
        for required in ("name", "dataset", "kind"):
            if required not in check:
                raise CheckDefinitionError(f"Check {index} in {path} has no {required}.")
        if check["kind"] not in CHECK_KINDS:
            raise CheckDefinitionError(
                f"Check {check['name']} has unknown kind {check['kind']!r}. Known kinds: {', '.join(CHECK_KINDS)}."
            )
    return checks


def evaluate(check: dict[str, Any], frame: DataFrameLike) -> CheckResult:
    name = check["name"]
    dataset = check["dataset"]
    kind = check["kind"]
    blocking = bool(check.get("blocking", True))

    def result(status: str, observed: Any, threshold: Any, detail: str = "") -> CheckResult:
        return CheckResult(
            name=name,
            dataset=dataset,
            kind=kind,
            status=status,
            observed=str(observed),
            threshold=str(threshold),
            blocking=blocking,
            detail=detail,
        )

    column = check.get("column")
    if kind in ("null_rate_max", "unique", "freshness_max_hours", "accepted_values"):
        if not column:
            return result("errored", "n/a", "n/a", f"{kind} needs a column.")
        if column not in frame.columns:
            return result("errored", "n/a", "n/a", f"Column {column} is absent from {dataset}.")

    total = frame.count()

    if kind == "row_count_min":
        minimum = int(check["value"])
        return result("passed" if total >= minimum else "failed", total, f">= {minimum}")

    if kind == "null_rate_max":
        if total == 0:
            return result(
                "errored", 0, check["value"], "Dataset is empty, so a null rate is undefined."
            )
        nulls = frame.filter(f"{column} IS NULL").count()
        rate = nulls / total
        limit = float(check["value"])
        return result("passed" if rate <= limit else "failed", round(rate, 6), f"<= {limit}")

    if kind == "unique":
        distinct = frame.select(column).distinct().count()
        return result("passed" if distinct == total else "failed", distinct, f"== {total} rows")

    if kind == "freshness_max_hours":
        hours = int(check["value"])
        stale = frame.filter(f"{column} < current_timestamp() - INTERVAL {hours} HOURS").count()
        return result(
            "passed" if stale == 0 else "failed",
            f"{stale} stale rows",
            f"0 older than {hours}h",
        )

    if kind == "accepted_values":
        allowed = check["value"]
        quoted = ", ".join(f"'{value}'" for value in allowed)
        violations = frame.filter(f"{column} NOT IN ({quoted})").count()
        return result("passed" if violations == 0 else "failed", f"{violations} violations", quoted)

    raise CheckDefinitionError(f"Unhandled check kind {kind!r}.")


def run_checks(
    checks: list[dict[str, Any]], datasets: dict[str, DataFrameLike]
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in checks:
        frame = datasets.get(check["dataset"])
        if frame is None:
            results.append(
                CheckResult(
                    name=check["name"],
                    dataset=check["dataset"],
                    kind=check["kind"],
                    status="errored",
                    observed="n/a",
                    threshold="n/a",
                    blocking=bool(check.get("blocking", True)),
                    detail=f"The pipeline produced no dataset named {check['dataset']}.",
                )
            )
            continue
        try:
            results.append(evaluate(check, frame))
        except Exception as error:  # noqa: BLE001 - report engine failures and block the load
            results.append(
                CheckResult(
                    name=check["name"],
                    dataset=check["dataset"],
                    kind=check["kind"],
                    status="errored",
                    observed="n/a",
                    threshold=str(check.get("value", "n/a")),
                    blocking=bool(check.get("blocking", True)),
                    detail=f"{type(error).__name__}: {error}",
                )
            )
    return results


def should_stop(results: list[CheckResult]) -> bool:
    """Blocking failures and any error stop the run. Warnings do not."""
    return any(
        result.status == "errored" or (result.status == "failed" and result.blocking)
        for result in results
    )


def report(results: list[CheckResult], run_id: str) -> str:
    return json.dumps(
        {
            "run_id": run_id,
            "passed": sum(1 for r in results if r.status == "passed"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "errored": sum(1 for r in results if r.status == "errored"),
            "checks": [asdict(result) for result in results],
        },
        indent=2,
    )
