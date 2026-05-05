from typing import Protocol

from domain.customer import Customer

OBSERVABILITY_FIXTURE_CUSTOMER_NAME = "Observability Smoke Customer"


class ObservabilityFixtureRepository(Protocol):
    def ensure_customer(self, *, name: str) -> Customer: ...


def ensure_observability_fixture_customer(
    *,
    fixtures: ObservabilityFixtureRepository,
) -> Customer:
    return fixtures.ensure_customer(name=OBSERVABILITY_FIXTURE_CUSTOMER_NAME)
