"""
smoke_test.py — Assert GET /health returns 200.

Prints "health ok" and exits 0 on success.
Exits non-zero if the app is not reachable or returns a non-200 status.

Usage:
    python scripts/smoke_test.py

Reads BASE_URL from environment (default: http://localhost:8000).
"""

import os
import sys

import httpx


def main() -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    url = f"{base_url}/health"

    try:
        response = httpx.get(url, timeout=10)
        if response.status_code == 200:
            print("health ok")
            sys.exit(0)
        else:
            print(
                f"ERROR: /health returned HTTP {response.status_code}", file=sys.stderr
            )
            sys.exit(1)
    except httpx.RequestError as exc:
        print(f"ERROR: could not reach {url}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
