"""
seed_data.py — Insert customers and orders into the database.

Volume is controlled by environment variables so the same script works across
all environments without modification:

  SEED_NUM_CUSTOMERS  default: 1_000   (local dev / CI)
  SEED_NUM_ORDERS     default: 10_000  (local dev / CI)

For QA against a real RDS instance, override before running:

  SEED_NUM_CUSTOMERS=50000 SEED_NUM_ORDERS=1000000 uv run python scripts/seed_data.py

Idempotent: skips insertion if rows already exist.

Billing email behaviour mirrors production:
- Registered customers always have an email (derived from their name + id).
- ~5% of orders are guest checkouts with no billing_email, reflecting orders
  placed before email collection was enforced.

Requires DATABASE_URL in environment or .env file.
"""

import os
import random
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# load_dotenv with override=False: env vars already set in the shell take
# precedence over .env values, matching the behaviour of the app's pydantic-settings.
load_dotenv(Path(__file__).parent.parent / ".env", override=False)

DATABASE_URL = os.environ["DATABASE_URL"]

NUM_CUSTOMERS = int(os.environ.get("SEED_NUM_CUSTOMERS", 1_000))
NUM_ORDERS = int(os.environ.get("SEED_NUM_ORDERS", 10_000))
GUEST_ORDER_RATE = 0.05  # ~5% of orders are guest checkouts with no billing_email
BATCH_SIZE = 5_000

STATUSES = ["SUBMITTED", "PAID", "CANCELLED"]

FIRST_NAMES = [
    "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry",
    "Iris", "Jack", "Karen", "Liam", "Mia", "Noah", "Olivia", "Paul",
    "Quinn", "Rachel", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zoe", "Aaron", "Bella", "Carlos", "Diana", "Ethan", "Fiona",
    "George", "Hannah", "Ivan", "Julia", "Kevin", "Laura", "Mike", "Nina",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
    "White", "Harris", "Martin", "Thompson", "Young", "Allen", "King",
    "Wright", "Scott", "Green", "Baker", "Adams", "Nelson", "Carter",
    "Mitchell", "Perez", "Roberts", "Turner", "Phillips", "Campbell",
    "Parker", "Evans", "Edwards", "Collins", "Stewart", "Morris",
]

EMAIL_DOMAINS = [
    "example.com", "mail.test", "demo.org", "sample.net", "test.io",
]


def random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def customer_email(name: str, customer_id: int) -> str:
    local = name.lower().replace(" ", ".") + str(customer_id)
    return f"{local}@{random.choice(EMAIL_DOMAINS)}"


def random_submitted_at() -> datetime:
    now = datetime.now(tz=timezone.utc)
    delta = timedelta(days=random.randint(0, 730), seconds=random.randint(0, 86400))
    return now - delta


def main() -> None:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    with engine.connect() as conn:
        # ------------------------------------------------------------------ #
        # Customers                                                            #
        # ------------------------------------------------------------------ #
        customer_count = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
        if customer_count and customer_count > 0:
            print(f"Customers already exist ({customer_count:,} rows) — skipping customer insertion.")
        else:
            print(f"Inserting {NUM_CUSTOMERS:,} customers in batches of {BATCH_SIZE:,}…")
            t0 = time.monotonic()
            inserted_customers = 0

            for batch_start in range(0, NUM_CUSTOMERS, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, NUM_CUSTOMERS)
                rows = [
                    {"name": random_name()}
                    for _ in range(batch_end - batch_start)
                ]
                conn.execute(text("INSERT INTO customers (name) VALUES (:name)"), rows)
                conn.commit()
                inserted_customers += len(rows)
                print(f"  customers: {inserted_customers:,}/{NUM_CUSTOMERS:,}")

            elapsed = time.monotonic() - t0
            print(f"Customers done in {elapsed:.1f}s.")

        # ------------------------------------------------------------------ #
        # Orders                                                               #
        # ------------------------------------------------------------------ #
        order_count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        if order_count and order_count > 0:
            print(f"Orders already exist ({order_count:,} rows) — skipping order insertion.")
        else:
            # Fetch all customer IDs so we can distribute orders across them
            print("Fetching customer IDs…")
            result = conn.execute(text("SELECT id, name FROM customers ORDER BY id"))
            customers = result.fetchall()  # list of (id, name) rows

            if not customers:
                print("ERROR: No customers found. Run seed without existing customers first.")
                raise SystemExit(1)

            print(f"Inserting {NUM_ORDERS:,} orders in batches of {BATCH_SIZE:,}…")
            t0 = time.monotonic()
            inserted_orders = 0

            for batch_start in range(0, NUM_ORDERS, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, NUM_ORDERS)
                rows = []
                for _ in range(batch_end - batch_start):
                    cust = random.choice(customers)
                    cust_id = cust[0]
                    cust_name = cust[1]
                    # Guest checkouts have no billing_email; registered customers always do.
                    is_guest = random.random() < GUEST_ORDER_RATE
                    billing_email = None if is_guest else customer_email(cust_name, cust_id)
                    rows.append({
                        "customer_id": cust_id,
                        # Decimal via string avoids float representation noise before
                        # the value reaches the NUMERIC(12,2) column.
                        "total_amount": Decimal(f"{random.uniform(1.00, 9999.99):.2f}"),
                        "status": random.choice(STATUSES),
                        "submitted_at": random_submitted_at(),
                        "billing_email": billing_email,
                    })

                conn.execute(
                    text(
                        "INSERT INTO orders "
                        "(customer_id, total_amount, status, submitted_at, billing_email) "
                        "VALUES (:customer_id, :total_amount, :status, :submitted_at, :billing_email)"
                    ),
                    rows,
                )
                conn.commit()
                inserted_orders += len(rows)
                print(f"  orders: {inserted_orders:,}/{NUM_ORDERS:,}")

            elapsed = time.monotonic() - t0
            print(f"Orders done in {elapsed:.1f}s.")

    print("Seed complete.")


if __name__ == "__main__":
    main()
