"""
verify_contract_ready.py — Check that the system is ready for the Contract phase.

Verifies two conditions:
  1. All backfill rows are present: every order with a non-null billing_email
     has a corresponding row in order_contact_email.
  2. READ_MODE is set to "new" in app_runtime_config.

Exits 0 if both conditions are met, 1 otherwise.

Usage:
    python scripts/verify_contract_ready.py

Reads DATABASE_URL from environment or .env file.
"""

import sys

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, text


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str


settings = Settings()


def main() -> None:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    ready = True

    with engine.connect() as conn:
        # ------------------------------------------------------------------ #
        # Check 1: All backfill rows are present                              #
        # Every order with a non-null billing_email must have a row in        #
        # order_contact_email.                                                 #
        #                                                                      #
        # If the Contract migration has already been applied, orders.billing_email
        # no longer exists and this check is vacuously satisfied — the column
        # was the source of truth and it's gone, meaning the migration is done.
        # ------------------------------------------------------------------ #
        col_exists = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'orders' AND column_name = 'billing_email'"
            )
        ).fetchone()

        if col_exists is None:
            print("OK: orders.billing_email has already been dropped (Contract phase complete).")
        else:
            missing_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM orders o "
                    "WHERE o.billing_email IS NOT NULL "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM order_contact_email oce WHERE oce.order_id = o.id"
                    ")"
                )
            ).scalar()

            if missing_count and missing_count > 0:
                print(f"FAIL: {missing_count:,} order(s) with billing_email have no row in order_contact_email.")
                ready = False
            else:
                print("OK: all backfill rows are present in order_contact_email.")

        # ------------------------------------------------------------------ #
        # Check 2: READ_MODE is "new"                                         #
        # ------------------------------------------------------------------ #
        read_mode = conn.execute(
            text("SELECT value FROM app_runtime_config WHERE key = 'READ_MODE'")
        ).scalar()

        if read_mode != "new":
            current = repr(read_mode) if read_mode is not None else "not set"
            print(f"FAIL: READ_MODE is {current}, expected 'new'.")
            ready = False
        else:
            print("OK: READ_MODE is 'new'.")

    if ready:
        print("Contract phase is ready.")
        sys.exit(0)
    else:
        print("Contract phase is NOT ready.")
        sys.exit(1)


if __name__ == "__main__":
    main()
