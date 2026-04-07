import datetime
from dataclasses import dataclass


@dataclass
class Customer:
    id: int
    name: str
    created_at: datetime.datetime
