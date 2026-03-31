from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Dropped in the Contract phase — nullable so the ORM works before and after the migration.
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )


class OrderContactEmailModel(Base):
    __tablename__ = "order_contact_email"

    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id"), primary_key=True)
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )


class AppRuntimeConfigModel(Base):
    __tablename__ = "app_runtime_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(100), nullable=False)
