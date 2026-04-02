import abc
from decimal import Decimal

from domain.order import Order, OrderStatus


class OrderRepository(abc.ABC):
    @abc.abstractmethod
    def create_order(
        self,
        customer_id: int,
        total_amount: Decimal,
        order_status: OrderStatus,
        billing_email: str | None,
    ) -> Order: ...

    @abc.abstractmethod
    def get_order(self, order_id: int) -> Order | None: ...


class ConfigStore(abc.ABC):
    @abc.abstractmethod
    def get(self, key: str) -> str | None: ...

    @abc.abstractmethod
    def set(self, key: str, value: str) -> None: ...
