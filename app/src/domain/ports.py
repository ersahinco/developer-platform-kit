from __future__ import annotations

import abc

from domain.order import Order


class OrderRepository(abc.ABC):
    @abc.abstractmethod
    def create_order(
        self,
        customer_id: int,
        total_amount: float,
        status: str,
        billing_email: str | None,
    ) -> Order: ...

    @abc.abstractmethod
    def get_order(self, order_id: int) -> Order | None: ...


class ConfigStore(abc.ABC):
    @abc.abstractmethod
    def get_read_mode(self) -> str: ...

    @abc.abstractmethod
    def set_read_mode(self, mode: str) -> None: ...
