from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette import status
from starlette.responses import JSONResponse


def health_payload() -> dict[str, str]:
    return {"status": "ok"}


def ready_payload() -> dict[str, object]:
    return {"status": "ready", "checks": {"database": "ok"}}


def unready_payload() -> dict[str, object]:
    return {"status": "unready", "checks": {"database": "unavailable"}}


def database_readiness_response(
    check: Callable[[], Any],
) -> dict[str, object] | JSONResponse:
    try:
        check()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=unready_payload(),
        )
    return ready_payload()
