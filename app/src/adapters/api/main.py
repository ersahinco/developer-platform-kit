import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from adapters.api.schemas import (
    CreateOrderRequest,
    HealthResponse,
    OrderResponse,
    ReadModeRequest,
    ReadModeResponse,
    WriteModeRequest,
    WriteModeResponse,
)
from db import get_db
from domain.ports import ConfigStore, OrderRepository


class _SuppressHealthChecks(logging.Filter):
    """Drop GET /health 200 from access logs.

    ALB probes every 15 s from each AZ, and the ECS container health check adds
    a third hit from 127.0.0.1 — together they produce ~4 log lines/min with no
    signal. Real errors on /health (non-200) still pass through.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ("GET /health" in msg and "200" in msg)


# Installed at module load time — runs once for the lifetime of the process.
logging.getLogger("uvicorn.access").addFilter(_SuppressHealthChecks())

app = FastAPI(title="db-migration-example")

DbDep = Annotated[Session, Depends(get_db)]


def get_order_repo(db: DbDep) -> OrderRepository:
    # Import here, not at module level — keeps the API adapter decoupled from
    # the DB adapter at import time. The port is the compile-time contract;
    # the concrete implementation is wired only at request time.
    from adapters.db.repository import SQLAlchemyOrderRepository

    return SQLAlchemyOrderRepository(session=db)


def get_config_store(db: DbDep) -> ConfigStore:
    from adapters.db.repository import SQLAlchemyConfigStore

    return SQLAlchemyConfigStore(session=db)


OrderRepoDep = Annotated[OrderRepository, Depends(get_order_repo)]
ConfigStoreDep = Annotated[ConfigStore, Depends(get_config_store)]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(body: CreateOrderRequest, repo: OrderRepoDep) -> OrderResponse:
    order = repo.create_order(
        customer_id=body.customer_id,
        total_amount=body.total_amount,
        order_status=body.status,
        billing_email=body.billing_email,
    )
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        total_amount=order.total_amount,
        status=order.order_status,
        submitted_at=order.submitted_at,
        created_at=order.created_at,
        billing_email=order.billing_email,
    )


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
