from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.release.verify_post_deploy as verify_post_deploy  # noqa: E402


def test_http_checks_require_health_ready_and_metrics(monkeypatch) -> None:
    def fake_get_json(base_url: str, path: str) -> tuple[int, dict[str, Any]]:
        responses = {
            "/health": (200, {"status": "ok"}),
            "/ready": (200, {"status": "ready", "checks": {"database": "ok"}}),
        }
        return responses[path]

    def fake_get_text(base_url: str, path: str) -> tuple[int, str]:
        assert path == "/metrics"
        return 200, "http_requests_total 1\nhttp_request_duration_seconds_count 1\n"

    monkeypatch.setattr(verify_post_deploy, "_get_json", fake_get_json)
    monkeypatch.setattr(verify_post_deploy, "_get_text", fake_get_text)

    results = verify_post_deploy._check_http("http://app.local")

    assert [result.ok for result in results] == [True, True, True]


def test_runtime_mode_check_compares_expected_value(monkeypatch) -> None:
    def fake_get_json(base_url: str, path: str) -> tuple[int, dict[str, Any]]:
        return 200, {"mode": "dual"}

    monkeypatch.setattr(verify_post_deploy, "_get_json", fake_get_json)

    assert verify_post_deploy._check_runtime_mode(
        "http://app.local", "/admin/write-mode", "dual", "WRITE_MODE"
    ).ok
    assert not verify_post_deploy._check_runtime_mode(
        "http://app.local", "/admin/write-mode", "new", "WRITE_MODE"
    ).ok


def test_ecs_checks_are_skipped_without_service_env(monkeypatch) -> None:
    monkeypatch.delenv("ECS_CLUSTER", raising=False)
    monkeypatch.delenv("ECS_SERVICE", raising=False)

    results = verify_post_deploy._check_ecs()

    assert len(results) == 1
    assert results[0].ok
    assert "skipped" in results[0].message


def test_ecs_checks_validate_primary_task_and_image(monkeypatch) -> None:
    monkeypatch.setenv("ECS_CLUSTER", "aws-sdlc-containers")
    monkeypatch.setenv("ECS_SERVICE", "app")
    monkeypatch.setenv("EXPECTED_IMAGE_TAG", "sha-test")

    def fake_aws_json(args: list[str], region: str) -> dict[str, Any]:
        if args[:2] == ["ecs", "describe-services"]:
            return {
                "services": [
                    {
                        "desiredCount": 1,
                        "runningCount": 1,
                        "taskDefinition": "arn:aws:ecs:task-definition/aws-sdlc-containers:7",
                        "deployments": [
                            {"status": "PRIMARY", "rolloutState": "COMPLETED"}
                        ],
                    }
                ]
            }
        if args[:2] == ["ecs", "describe-task-definition"]:
            return {
                "taskDefinition": {
                    "family": "aws-sdlc-containers",
                    "containerDefinitions": [
                        {
                            "name": "app",
                            "image": "example.dkr.ecr/app:sha-test",
                        }
                    ],
                }
            }
        raise AssertionError(f"unexpected aws call: {json.dumps(args)}")

    monkeypatch.setattr(verify_post_deploy, "_aws_json", fake_aws_json)

    results = verify_post_deploy._check_ecs()

    assert all(result.ok for result in results)
