import asyncio
import json
import logging
import os
import re
import time
import uuid
from typing import Annotated
from typing import cast

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import JSONResponse
from starlette.responses import Response

from api.db import engine, get_db
from api.schemas import (
    CreateOrderRequest,
    CustomerResponse,
    HealthResponse,
    OrderResponse,
    ReadinessResponse,
    ReadModeRequest,
    ReadModeResponse,
    WriteModeRequest,
    WriteModeResponse,
)
from api.telemetry import configure_tracing
from application.idempotency import IdempotencyRepository, order_request_hash
from application.observability import (
    ObservabilityFixtureRepository,
    ensure_observability_fixture_customer as ensure_fixture_customer,
)
from domain.order import ReadModeValue, WriteModeValue
from application.order_submission import (
    CustomerNotFoundError,
    InvalidOrderAmountError,
    submit_order,
)
from application.ports import ConfigStore, CustomerRepository, OrderRepository


class _SuppressLowValueAccessLogs(logging.Filter):
    """Drop successful probe/scrape access logs.

    ALB probes every 15 s from each AZ, and the ECS container health check adds
    a third hit from 127.0.0.1 — together they produce ~4 log lines/min with no
    signal. Prometheus scrapes `/metrics` every 15 s and adds a similar stream
    of successful access logs. Real non-200 responses still pass through.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 5:
            method = record.args[1]
            path = record.args[2]
            status_code = record.args[4]
            if method == "GET" and path in {"/health", "/metrics"}:
                if isinstance(status_code, int):
                    return not (200 <= status_code < 300)
                if isinstance(status_code, str):
                    try:
                        return not (200 <= int(status_code) < 300)
                    except ValueError:
                        pass

        msg = record.getMessage()
        is_success = re.search(r'"\s+2\d\d\b', msg) is not None
        is_low_value_path = '"GET /health ' in msg or '"GET /metrics ' in msg
        return not (is_success and is_low_value_path)


# Installed at module load time — runs once for the lifetime of the process.
logging.getLogger("uvicorn.access").addFilter(_SuppressLowValueAccessLogs())

app = FastAPI(title="aws-sdlc-containers")
configure_tracing(app=app, engine=engine)

DbDep = Annotated[Session, Depends(get_db)]

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests by method, route, and status code.",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency by method and route.",
    ["method", "route"],
)


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


def _request_id(request: Request) -> str:
    request_id = request.headers.get("x-request-id", "").strip()
    return request_id or uuid.uuid4().hex


def _rollout_fault_paths() -> set[str]:
    raw_paths = os.getenv("ROLLOUT_DRILL_FAULT_PATHS", "/ready")
    return {path.strip() for path in raw_paths.split(",") if path.strip()}


def _rollout_fault_status_code() -> int:
    try:
        status_code = int(os.getenv("ROLLOUT_DRILL_FAULT_STATUS_CODE", "503"))
    except ValueError:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if 100 <= status_code <= 599:
        return status_code
    return status.HTTP_503_SERVICE_UNAVAILABLE


def _rollout_fault_delay_seconds() -> float:
    try:
        delay = float(os.getenv("ROLLOUT_DRILL_FAULT_DELAY_SECONDS", "3"))
    except ValueError:
        return 3.0
    return max(0.0, delay)


def _rollout_fault_mode_for(request: Request) -> str:
    mode = os.getenv("ROLLOUT_DRILL_FAULT_MODE", "off").strip().lower()
    if mode not in {"error", "latency"}:
        return "off"
    if request.url.path not in _rollout_fault_paths():
        return "off"
    return mode


@app.middleware("http")
async def observe_requests(request: Request, call_next) -> Response:
    request_id = _request_id(request)
    request.state.request_id = request_id

    if request.url.path == "/metrics":
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    started_at = time.perf_counter()
    try:
        fault_mode = _rollout_fault_mode_for(request)
        if fault_mode == "latency":
            await asyncio.sleep(_rollout_fault_delay_seconds())
            response = await call_next(request)
        elif fault_mode == "error":
            response = JSONResponse(
                status_code=_rollout_fault_status_code(),
                content={"detail": "rollout drill fault injection"},
            )
        else:
            response = await call_next(request)
    except Exception:
        route = _route_label(request)
        REQUEST_COUNT.labels(request.method, route, "500").inc()
        REQUEST_LATENCY.labels(request.method, route).observe(
            time.perf_counter() - started_at
        )
        raise

    route = _route_label(request)
    REQUEST_COUNT.labels(request.method, route, str(response.status_code)).inc()
    elapsed_seconds = time.perf_counter() - started_at
    REQUEST_LATENCY.labels(request.method, route).observe(elapsed_seconds)
    response.headers["X-Request-ID"] = request_id
    print(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status_code": response.status_code,
                "duration_ms": round(elapsed_seconds * 1000, 3),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return response


def get_order_repo(db: DbDep) -> OrderRepository:
    # Import here, not at module level — keeps the API adapter decoupled from
    # the DB adapter at import time. The port is the compile-time contract;
    # the concrete implementation is wired only at request time.
    from infrastructure.db.repository import SQLAlchemyOrderRepository

    return SQLAlchemyOrderRepository(session=db)


def get_customer_repo(db: DbDep) -> CustomerRepository:
    from infrastructure.db.repository import SQLAlchemyCustomerRepository

    return SQLAlchemyCustomerRepository(session=db)


def get_idempotency_repo(db: DbDep) -> IdempotencyRepository:
    from infrastructure.db.repository import SQLAlchemyIdempotencyRepository

    return SQLAlchemyIdempotencyRepository(session=db)


def get_config_store(db: DbDep) -> ConfigStore:
    from infrastructure.db.repository import SQLAlchemyConfigStore

    return SQLAlchemyConfigStore(session=db)


def get_observability_fixture_repo(db: DbDep) -> ObservabilityFixtureRepository:
    from infrastructure.db.repository import (
        SQLAlchemyObservabilityFixtureRepository,
    )

    return SQLAlchemyObservabilityFixtureRepository(session=db)


def _begin_idempotent_request(
    *,
    idempotency: IdempotencyRepository,
    key: str,
    request_hash: str,
):
    deadline = time.monotonic() + 5
    while True:
        result = idempotency.begin(key=key, request_hash=request_hash)
        if result.status != "processing" or time.monotonic() >= deadline:
            return result
        time.sleep(0.05)


OrderRepoDep = Annotated[OrderRepository, Depends(get_order_repo)]
CustomerRepoDep = Annotated[CustomerRepository, Depends(get_customer_repo)]
IdempotencyRepoDep = Annotated[IdempotencyRepository, Depends(get_idempotency_repo)]
ConfigStoreDep = Annotated[ConfigStore, Depends(get_config_store)]
ObservabilityFixtureDep = Annotated[
    ObservabilityFixtureRepository,
    Depends(get_observability_fixture_repo),
]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ready", response_model=ReadinessResponse)
def ready(db: DbDep) -> ReadinessResponse | JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unready", "checks": {"database": "unavailable"}},
        )

    return ReadinessResponse(status="ready", checks={"database": "ok"})


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, repo: CustomerRepoDep) -> CustomerResponse:
    customer = repo.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return CustomerResponse(
        id=customer.id,
        name=customer.name,
        created_at=customer.created_at,
    )


@app.post("/admin/observability-fixture", response_model=CustomerResponse)
def ensure_observability_fixture_customer(
    fixtures: ObservabilityFixtureDep,
) -> CustomerResponse:
    customer = ensure_fixture_customer(fixtures=fixtures)
    return CustomerResponse(
        id=customer.id,
        name=customer.name,
        created_at=customer.created_at,
    )


@app.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(
    body: CreateOrderRequest,
    repo: OrderRepoDep,
    customers: CustomerRepoDep,
    idempotency: IdempotencyRepoDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderResponse | JSONResponse:
    request_hash = order_request_hash(
        customer_id=body.customer_id,
        total_amount=body.total_amount,
        billing_email=str(body.billing_email) if body.billing_email else None,
    )
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 200:
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key must be between 1 and 200 characters",
            )
        begin = _begin_idempotent_request(
            idempotency=idempotency,
            key=idempotency_key,
            request_hash=request_hash,
        )
        if begin.status == "conflict":
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key was already used with a different request",
            )
        if begin.status == "replay":
            return JSONResponse(
                status_code=begin.response_status_code or status.HTTP_201_CREATED,
                content=begin.response_payload or {},
            )
        if begin.status == "processing":
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key is still processing",
            )

    try:
        order = submit_order(
            customer_id=body.customer_id,
            total_amount=body.total_amount,
            billing_email=str(body.billing_email) if body.billing_email else None,
            customers=customers,
            orders=repo,
        )
    except CustomerNotFoundError as exc:
        if idempotency_key is not None:
            payload: dict[str, object] = {"detail": str(exc)}
            idempotency.complete(
                key=idempotency_key,
                response_status_code=status.HTTP_404_NOT_FOUND,
                response_payload=payload,
            )
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidOrderAmountError as exc:
        if idempotency_key is not None:
            payload = {"detail": str(exc)}
            idempotency.complete(
                key=idempotency_key,
                response_status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                response_payload=payload,
            )
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=payload,
            )
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    response = OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        total_amount=order.total_amount,
        status=order.order_status,
        submitted_at=order.submitted_at,
        created_at=order.created_at,
        billing_email=order.billing_email,
    )
    if idempotency_key is not None:
        payload = cast(dict[str, object], response.model_dump(mode="json"))
        idempotency.complete(
            key=idempotency_key,
            response_status_code=status.HTTP_201_CREATED,
            response_payload=payload,
        )
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=payload)

    return response


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, repo: OrderRepoDep) -> OrderResponse:
    order = repo.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        total_amount=order.total_amount,
        status=order.order_status,
        submitted_at=order.submitted_at,
        created_at=order.created_at,
        billing_email=order.billing_email,
    )


@app.post("/admin/read-mode", response_model=ReadModeResponse)
def set_read_mode(body: ReadModeRequest, config: ConfigStoreDep) -> ReadModeResponse:
    """Switch READ_MODE at runtime without redeployment.

    Persists to app_runtime_config so all instances pick it up within one TTL
    window (5 s). Used during the backfill → switch → contract sequence to move
    reads from orders.billing_email to order_contact_email.
    """
    config.set("READ_MODE", body.mode)
    return ReadModeResponse(mode=body.mode)


@app.get("/admin/read-mode", response_model=ReadModeResponse)
def get_read_mode(config: ConfigStoreDep) -> ReadModeResponse:
    mode = config.get("READ_MODE")
    if mode not in ("legacy", "new"):
        raise HTTPException(status_code=503, detail="READ_MODE is not configured")
    return ReadModeResponse(mode=cast(ReadModeValue, mode))


@app.post("/admin/write-mode", response_model=WriteModeResponse)
def set_write_mode(body: WriteModeRequest, config: ConfigStoreDep) -> WriteModeResponse:
    """Switch WRITE_MODE at runtime without redeployment.

    Persists to app_runtime_config so all instances pick it up within one TTL
    window (5 s). Used to advance the write path through the migration sequence:
      legacy → dual  (after expand phase, before backfill complete)
      dual   → new   (after backfill verified, before contract phase)
    """
    config.set("WRITE_MODE", body.mode)
    return WriteModeResponse(mode=body.mode)


@app.get("/admin/write-mode", response_model=WriteModeResponse)
def get_write_mode(config: ConfigStoreDep) -> WriteModeResponse:
    mode = config.get("WRITE_MODE")
    if mode not in ("legacy", "dual", "new"):
        raise HTTPException(status_code=503, detail="WRITE_MODE is not configured")
    return WriteModeResponse(mode=cast(WriteModeValue, mode))
