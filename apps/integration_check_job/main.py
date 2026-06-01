import datetime
import json
from pathlib import Path
from typing import Any
from urllib import error
from urllib import request

from integration_check_job.config import settings

INTEGRATION_CHECK_JOB_NAME = "integration_check"


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def parse_targets(value: str) -> list[dict[str, str]]:
    stripped = value.strip()
    if not stripped:
        return []

    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise ValueError("INTEGRATION_CHECK_TARGETS JSON must be a list")
        return [_target_from_json(index, item) for index, item in enumerate(parsed)]

    targets = []
    for index, item in enumerate(part.strip() for part in stripped.split(",")):
        if not item:
            continue
        if "=" in item:
            name, url = item.split("=", 1)
        else:
            name, url = f"target-{index + 1}", item
        targets.append(_target(stripped_name=name, stripped_url=url))
    return targets


def _target_from_json(index: int, item: object) -> dict[str, str]:
    if isinstance(item, str):
        return _target(stripped_name=f"target-{index + 1}", stripped_url=item)
    if not isinstance(item, dict):
        raise ValueError("integration check targets must be strings or objects")
    name = item.get("name", f"target-{index + 1}")
    url = item.get("url")
    if not isinstance(name, str) or not isinstance(url, str):
        raise ValueError("integration check target objects require string name and url")
    return _target(stripped_name=name, stripped_url=url)


def _target(*, stripped_name: str, stripped_url: str) -> dict[str, str]:
    name = stripped_name.strip()
    url = stripped_url.strip()
    if not name:
        raise ValueError("integration check target name cannot be empty")
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"integration check target {name} must use http or https")
    return {"name": name, "url": url}


def check_targets(
    targets: list[dict[str, str]],
    *,
    timeout_seconds: float,
    opener: Any | None = None,
) -> list[dict[str, Any]]:
    urlopen = opener or request.urlopen
    results: list[dict[str, Any]] = []
    for target in targets:
        status_code: int | None = None
        error_message: str | None = None
        try:
            with urlopen(target["url"], timeout=timeout_seconds) as response:
                status_code = int(response.status)
        except error.HTTPError as exc:
            status_code = int(exc.code)
            error_message = str(exc)
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)

        passed = status_code is not None and 200 <= status_code < 400
        result: dict[str, Any] = {
            "name": target["name"],
            "url": target["url"],
            "status": "passed" if passed else "failed",
        }
        if status_code is not None:
            result["status_code"] = status_code
        if error_message is not None:
            result["error"] = error_message
        results.append(result)
    return results


def run_checks(
    *,
    targets: str | None = None,
    output_dir: str | None = None,
    run_id: str | None = None,
    timeout_seconds: float | None = None,
    opener: Any | None = None,
) -> dict[str, Any]:
    captured_at = _utc_now()
    effective_run_id = run_id or settings.integration_check_run_id
    if effective_run_id is None:
        effective_run_id = captured_at.strftime("%Y%m%dT%H%M%SZ")

    target_list = parse_targets(
        settings.integration_check_targets if targets is None else targets
    )
    results = check_targets(
        target_list,
        timeout_seconds=timeout_seconds
        if timeout_seconds is not None
        else settings.integration_check_timeout_seconds,
        opener=opener,
    )
    failed_count = sum(1 for result in results if result["status"] != "passed")
    status = "succeeded" if failed_count == 0 else "failed"
    event: dict[str, Any] = {
        "event": "integration_check_succeeded"
        if status == "succeeded"
        else "integration_check_failed",
        "job_name": INTEGRATION_CHECK_JOB_NAME,
        "run_id": effective_run_id,
        "status": status,
        "checked_count": len(results),
        "failed_count": failed_count,
        "captured_at": captured_at.isoformat(),
        "results": results,
    }

    output_root = Path(output_dir or settings.integration_check_output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    output_path = output_root / f"{effective_run_id}.json"
    event["output_path"] = str(output_path)
    output_path.write_text(
        json.dumps(event, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(event, sort_keys=True), flush=True)
    return event


def main() -> None:
    event = run_checks()
    if event["status"] != "succeeded":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
