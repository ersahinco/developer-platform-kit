import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from domain.order import OrderStatus


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Decimal matches the Numeric(12,2) column type and the domain/schema contract.
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Physical column name is 'status'; mapped as order_status in Python so application
    # code is stable across any future rename migration.
    order_status: Mapped[OrderStatus] = mapped_column(
        "status", String(32), nullable=False
    )
    submitted_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )
    # Present in legacy/dual WRITE_MODE phases; dropped in the contract phase.
    # Mapped as Optional so the model works after the column is gone.
    billing_email: Mapped[str | None] = mapped_column(String(255))


class OrderContactEmailModel(Base):
    __tablename__ = "order_contact_email"

    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), primary_key=True
    )
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )


class AppRuntimeConfigModel(Base):
    __tablename__ = "app_runtime_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(100), nullable=False)


class CustomerModel(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )
