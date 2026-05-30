from __future__ import annotations

from scripts.ci import observe_ecs_rollout


def _service(
    *,
    rollout_state: str = "IN_PROGRESS",
    desired: int = 1,
    running: int = 1,
    pending: int = 0,
) -> dict[str, object]:
    return {
        "serviceName": "api",
        "desiredCount": desired,
        "runningCount": running,
        "pendingCount": pending,
        "deployments": [
            {
                "status": "PRIMARY",
                "taskDefinition": "arn:aws:ecs:region:123:task-definition/app:42",
                "rolloutState": rollout_state,
                "desiredCount": desired,
                "runningCount": running,
                "pendingCount": pending,
                "failedTasks": 0,
            }
        ],
        "events": [
            {
                "createdAt": "2026-05-29T15:00:00Z",
                "message": "(service api) deployment completed.",
            }
        ],
    }


def test_service_is_stable_requires_completed_primary_and_counts() -> None:
    assert observe_ecs_rollout.service_is_stable(_service(rollout_state="COMPLETED"))
    assert not observe_ecs_rollout.service_is_stable(
        _service(rollout_state="IN_PROGRESS")
    )
    assert not observe_ecs_rollout.service_is_stable(
        _service(rollout_state="COMPLETED", desired=1, running=0, pending=1)
    )


def test_rollout_line_includes_timing_deployment_and_target_health() -> None:
    line = observe_ecs_rollout.rollout_line(
        _service(rollout_state="COMPLETED"),
        elapsed_seconds=123,
        target_health=["target-group:healthy=1"],
    )

    assert "[ 123s]" in line
    assert "PRIMARY app:42 rollout=COMPLETED" in line
    assert "targets=[target-group:healthy=1]" in line


def test_target_health_summary_counts_states() -> None:
    document = {
        "TargetHealthDescriptions": [
            {"TargetHealth": {"State": "healthy"}},
            {"TargetHealth": {"State": "initial"}},
            {"TargetHealth": {"State": "healthy"}},
        ]
    }

    assert observe_ecs_rollout.target_health_summary(document) == "healthy=2, initial=1"


def test_markdown_summary_includes_recent_service_events() -> None:
    summary = observe_ecs_rollout.markdown_summary(
        cluster="cluster",
        service="api",
        task_definition="arn:aws:ecs:region:123:task-definition/app:42",
        elapsed_seconds=12,
        stable=True,
        service_document={"services": [_service(rollout_state="COMPLETED")]},
        target_health=["target-group:healthy=1"],
    )

    assert "### ECS rollout" in summary
    assert "- Status: completed" in summary
    assert "- Elapsed: 12s" in summary
    assert "`app:42`" in summary
    assert "(service api) deployment completed." in summary
