from __future__ import annotations

import datetime
import json
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from pydantic import BaseModel
from pydantic import Field
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Counter
from prometheus_client import generate_latest
from prometheus_client import Histogram
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from starlette.responses import Response
import uvicorn

from application.booking import BookingRepository
from application.booking import reserve_slot
from booking_api.config import settings
from infrastructure.db.bookings import SQLAlchemyBookingRepository
from infrastructure.db.session import ping_database
from infrastructure.db.session import transaction_pool_engine_and_session_factory
from infrastructure.http_health import database_readiness_response
from infrastructure.http_health import health_payload
from infrastructure.http_observability import request_observability_middleware
from infrastructure.workload_observability import ensure_workload_info_metric

WORKLOAD_NAME = "booking_api"
WORKLOAD_CLASS = "internal-service"

REQUEST_COUNT = Counter(
    "booking_api_http_requests_total",
    "Booking API requests by method, route, and status code.",
    ["method", "route", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "booking_api_http_request_duration_seconds",
    "Booking API request latency by method and route.",
    ["method", "route"],
)
BOOKING_ATTEMPTS = Counter(
    "booking_attempts_total",
    "Booking attempts by outcome.",
    ["outcome"],
)
ensure_workload_info_metric(workload=WORKLOAD_NAME, workload_class=WORKLOAD_CLASS)

engine, SessionLocal = transaction_pool_engine_and_session_factory(
    str(settings.database_url)
)


class BookingRequest(BaseModel):
    resource_id: str = Field(min_length=1, max_length=200)
    starts_at: datetime.datetime
    customer_id: str = Field(min_length=1, max_length=200)


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


DbDep = Annotated[Session, Depends(get_db)]


def get_booking_repository(db: DbDep) -> BookingRepository:
    return SQLAlchemyBookingRepository(db)


BookingRepoDep = Annotated[BookingRepository, Depends(get_booking_repository)]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(title="booking-api", lifespan=lifespan)


def _http_request_event(
    request: Request,
    response: Response,
    request_id: str,
    elapsed_seconds: float,
) -> dict[str, object]:
    return {
        "workload": WORKLOAD_NAME,
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "route": getattr(request.scope.get("route"), "path", request.url.path),
        "status": "succeeded" if response.status_code < 500 else "failed",
        "status_code": response.status_code,
        "duration_ms": round(elapsed_seconds * 1000, 3),
    }


app.middleware("http")(
    request_observability_middleware(
        request_count=REQUEST_COUNT,
        request_latency=REQUEST_LATENCY,
        event_payload=_http_request_event,
    )
)


@app.get("/health")
def health() -> dict[str, str]:
    return health_payload()


@app.get("/ready", response_model=None)
def ready() -> dict[str, object] | JSONResponse:
    def check() -> None:
        with SessionLocal() as session:
            ping_database(session)

    return database_readiness_response(check)


@app.post("/bookings", status_code=201, response_model=None)
def create_booking(
    payload: BookingRequest, repository: BookingRepoDep
) -> dict[str, object] | JSONResponse:
    try:
        result = reserve_slot(
            resource_id=payload.resource_id,
            starts_at=payload.starts_at,
            customer_id=payload.customer_id,
            repository=repository,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    BOOKING_ATTEMPTS.labels(outcome=result.status).inc()
    event = {
        "workload": WORKLOAD_NAME,
        "event": f"booking_{result.status}",
        "status": result.status,
        "resource_id": payload.resource_id,
        "starts_at": payload.starts_at.isoformat(),
    }
    print(json.dumps(event, sort_keys=True), flush=True)
    if result.booking is None:
        return JSONResponse(
            status_code=409,
            content={
                "status": "conflict",
                "detail": "resource is already booked for this slot",
                "resource_id": payload.resource_id,
                "starts_at": payload.starts_at.isoformat(),
            },
        )
    return {
        "status": "reserved",
        "booking_id": result.booking.booking_id,
        "resource_id": result.booking.slot.resource_id,
        "starts_at": result.booking.slot.starts_at,
        "customer_id": result.booking.customer_id,
    }


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)


if __name__ == "__main__":
    main()
