"""
set_runtime_config.py — Set a runtime config flag via the admin API.

Usage:
    python scripts/set_runtime_config.py <flag> <value>

    <flag>  write-mode | read-mode
    <value> depends on the flag:
              write-mode: legacy | dual | new
              read-mode:  legacy | new

Reads BASE_URL from environment (default: http://localhost:8000).
Exits 0 on success, non-zero on error.
"""

import os
import sys

import httpx

_VALID_FLAGS = {"write-mode", "read-mode"}


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: python scripts/set_runtime_config.py <flag> <value>",
            file=sys.stderr,
        )
        print(f"  flag:  {' | '.join(sorted(_VALID_FLAGS))}", file=sys.stderr)
        sys.exit(1)

    flag, value = sys.argv[1], sys.argv[2]

    if flag not in _VALID_FLAGS:
        print(
            f"ERROR: unknown flag {flag!r}. Must be one of: {', '.join(sorted(_VALID_FLAGS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    url = f"{base_url}/admin/{flag}"

    try:
        response = httpx.post(url, json={"mode": value}, timeout=10)
        print(f"HTTP {response.status_code}")
        print(response.text)
        if response.is_error:
            sys.exit(1)
    except httpx.RequestError as exc:
        print(f"ERROR: could not reach {url}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
