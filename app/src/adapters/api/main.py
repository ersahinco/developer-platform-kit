from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from adapters.api.schemas import CreateOrderRequest, HealthResponse, OrderResponse, SetReadModeRequest, SetReadModeResponse
from config import settings
from db import get_db
from domain.ports import ConfigStore, OrderRepository

app = FastAPI(title="db-migration-example")

_VALID_READ_MODES = {"legacy", "new"}

DbDep = Annotated[Session, Depends(get_db)]


def get_config_store(db: DbDep) -> ConfigStore:
    from adapters.db.repository import SQLAlchemyConfigStore
    return SQLAlchemyConfigStore(session=db, settings=settings)


ConfigStoreDep = Annotated[ConfigStore, Depends(get_config_store)]


def get_order_repo(db: DbDep, config_store: ConfigStoreDep) -> OrderRepository:
    from adapters.db.repository import SQLAlchemyOrderRepository
    return SQLAlchemyOrderRepository(session=db, settings=settings, config_store=config_store)


OrderRepoDep = Annotated[OrderRepository, Depends(get_order_repo)]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(body: CreateOrderRequest, repo: OrderRepoDep) -> OrderResponse:
    order = repo.create_order(
        customer_id=body.customer_id,
        total_amount=body.total_amount,
        status=body.status,
        billing_email=body.billing_email,
    )
    return OrderResponse(**order.__dict__)


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, repo: OrderRepoDep) -> OrderResponse:
    order = repo.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return OrderResponse(**order.__dict__)


@app.post("/admin/read-mode", response_model=SetReadModeResponse)
def set_read_mode(body: SetReadModeRequest, config_store: ConfigStoreDep) -> SetReadModeResponse:
    if body.mode not in _VALID_READ_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid mode {body.mode!r}. Must be one of {sorted(_VALID_READ_MODES)}.")
    config_store.set_read_mode(body.mode)
    return SetReadModeResponse(read_mode=body.mode)
