from __future__ import annotations

from typing import Any

DATABASE_COMPOSED_ENV_NAMES = frozenset({"DATABASE_URL"})

# These names are declared in platform/workloads.json because operators can set
# them, but the app hosts have deterministic defaults when ECS does not inject
# them into the base task definition.
AWS_APP_DEFAULT_ENV_NAMES_BY_WORKLOAD = {
    "event_consumer": frozenset(
        {
            "ASYNC_EVENT_WORKER_MODE",
            "ASYNC_EVENT_WORKER_RUN_ONCE",
            "OUTBOX_RELAY_BATCH_SIZE",
            "OUTBOX_RELAY_IDLE_SLEEP_SECONDS",
        }
    ),
    "backfill_worker": frozenset(
        {
            "BACKFILL_BATCH_SIZE",
            "BACKFILL_SLEEP_MS",
            "BACKFILL_MAX_BATCHES",
        }
    ),
    "data_export_job": frozenset(
        {
            "DATA_EXPORT_OUTPUT_DIR",
            "DATA_EXPORT_RUN_ID",
            "DATA_EXPORT_DATE",
        }
    ),
}

AWS_RUN_TASK_OVERRIDE_ENV_NAMES_BY_WORKLOAD = {
    "operational_snapshot_job": frozenset({"OPERATIONAL_SNAPSHOT_RUN_ID"}),
}


def workload_name(workload: dict[str, Any]) -> str:
    name = workload.get("name")
    return str(name) if name else ""


def declared_env_names(workload: dict[str, Any]) -> set[str]:
    config = workload.get("config")
    if not isinstance(config, dict):
        return set()
    env = config.get("env")
    if not isinstance(env, list):
        return set()
    return {str(name) for name in env if name}


def aws_env_realization_exception_names(workload: dict[str, Any]) -> set[str]:
    name = workload_name(workload)
    names: set[str] = set()
    if isinstance(workload.get("database"), dict):
        names.update(DATABASE_COMPOSED_ENV_NAMES)
    names.update(AWS_APP_DEFAULT_ENV_NAMES_BY_WORKLOAD.get(name, frozenset()))
    names.update(AWS_RUN_TASK_OVERRIDE_ENV_NAMES_BY_WORKLOAD.get(name, frozenset()))
    return names
