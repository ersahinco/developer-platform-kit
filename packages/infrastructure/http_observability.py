from __future__ import annotations

import inspect
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.responses import Response


BeforeRequestHook = Callable[[Request], Response | None | Awaitable[Response | None]]
EventPayloadBuilder = Callable[[Request, Response, str, float], dict[str, Any]]


def route_label(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


def ensure_request_id(request: Request) -> str:
    request_id = request.headers.get("x-request-id", "").strip()
    resolved = request_id or uuid.uuid4().hex
    request.state.request_id = resolved
    return resolved


def request_observability_middleware(
    *,
    request_count: Counter,
    request_latency: Histogram,
    event_payload: EventPayloadBuilder,
    before_request: BeforeRequestHook | None = None,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = ensure_request_id(request)

        if request.url.path == "/metrics":
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        started_at = time.perf_counter()
        try:
            response: Response | None = None
            if before_request is not None:
                hook_response = before_request(request)
                if inspect.isawaitable(hook_response):
                    response = await hook_response
                else:
                    response = hook_response
            if response is None:
                response = await call_next(request)
        except Exception:
            route = route_label(request)
            request_count.labels(request.method, route, "500").inc()
            request_latency.labels(request.method, route).observe(
                time.perf_counter() - started_at
            )
            raise

        route = route_label(request)
        request_count.labels(request.method, route, str(response.status_code)).inc()
        elapsed_seconds = time.perf_counter() - started_at
        request_latency.labels(request.method, route).observe(elapsed_seconds)
        response.headers["X-Request-ID"] = request_id
        print(
            json.dumps(
                event_payload(request, response, request_id, elapsed_seconds),
                sort_keys=True,
            ),
            flush=True,
        )
        return response

    return middleware
