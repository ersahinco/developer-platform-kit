import abc
from decimal import Decimal

from aws_sdlc_domain.customer import Customer
from aws_sdlc_domain.order import Order


class OrderRepository(abc.ABC):
    @abc.abstractmethod
    def create_order(
        self,
        customer_id: int,
        total_amount: Decimal,
        billing_email: str | None,
    ) -> Order: ...

    @abc.abstractmethod
    def get_order(self, order_id: int) -> Order | None: ...


class CustomerRepository(abc.ABC):
    @abc.abstractmethod
    def get_customer(self, customer_id: int) -> Customer | None: ...


class ConfigStore(abc.ABC):
    @abc.abstractmethod
    def get(self, key: str) -> str | None: ...

    @abc.abstractmethod
    def set(self, key: str, value: str) -> None: ...
