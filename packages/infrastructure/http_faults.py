from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette import status
from starlette.responses import JSONResponse, Response


SleepFn = Callable[[float], Awaitable[None]]


def fault_mode_for(*, mode: str, path: str, configured_paths: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in {"error", "latency"}:
        return "off"
    allowed_paths = {
        candidate.strip()
        for candidate in configured_paths.split(",")
        if candidate.strip()
    }
    if path not in allowed_paths:
        return "off"
    return normalized


def fault_status_code(value: int) -> int:
    if 100 <= value <= 599:
        return value
    return status.HTTP_503_SERVICE_UNAVAILABLE


def fault_delay_seconds(value: float) -> float:
    return max(0.0, value)


async def maybe_build_fault_response(
    *,
    mode: str,
    path: str,
    configured_paths: str,
    status_code: int,
    delay_seconds: float,
    sleep: SleepFn,
) -> Response | None:
    resolved_mode = fault_mode_for(
        mode=mode,
        path=path,
        configured_paths=configured_paths,
    )
    if resolved_mode == "latency":
        await sleep(fault_delay_seconds(delay_seconds))
        return None
    if resolved_mode == "error":
        return JSONResponse(
            status_code=fault_status_code(status_code),
            content={"detail": "rollout drill fault injection"},
        )
    return None
