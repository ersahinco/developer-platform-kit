"""
switch_read_mode.py — Call POST /admin/read-mode with the given mode.

Prints the response status code and body, then exits 0 on success.
Exits non-zero if the request fails or the server returns an error status.

Usage:
    python scripts/switch_read_mode.py <mode>

    <mode> must be "legacy" or "new".

Reads BASE_URL from environment (default: http://localhost:8000).
"""

import os
import sys

import httpx


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/switch_read_mode.py <mode>", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    url = f"{base_url}/admin/read-mode"

    try:
        response = httpx.post(url, json={"mode": mode}, timeout=10)
        print(f"HTTP {response.status_code}")
        print(response.text)
        if response.is_error:
            sys.exit(1)
    except httpx.RequestError as exc:
        print(f"ERROR: could not reach {url}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
