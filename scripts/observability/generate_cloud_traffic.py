"""
generate_cloud_traffic.py — Produce a small representative cloud traffic burst.

This is intentionally tiny: it exercises readiness, runtime mode reads,
customer lookup, order creation, order readback, a controlled 404, and metrics.
The goal is to make Grafana/Loki/Prometheus panels visibly move without running
large data jobs or changing runtime modes.

Environment:
    BASE_URL         Optional absolute primary edge URL.
    PRIMARY_EDGE_BASE_URL
                     Optional alias for BASE_URL.
    ROOT_DOMAIN      Optional root domain used to derive the primary edge URL.
    PRIMARY_EDGE_HOSTNAME_LABEL
                     Optional primary edge hostname label. If absent, use
                     platform workload metadata.
    TOKEN            Optional bearer token. If absent, read from Secrets Manager.
    AUTH_TOKEN       TOKEN alias
    AWS_REGION       Default: eu-central-1
    STACK_NAME       Used to derive PRIMARY_EDGE_TOKEN_SECRET when needed.
    PRIMARY_EDGE_TOKEN_SECRET
                     Optional explicit secret id.
    CUSTOMER_ID      Optional exact customer id.
    CUSTOMER_ID_CANDIDATES
                     Optional comma-separated ids to probe when CUSTOMER_ID is absent.
    ORDER_COUNT      Default: 3
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse

import httpx
from scripts.platform.workload_read_model import primary_edge_service_workload
from scripts.platform.workload_read_model import workload_hostname_label


@dataclass(frozen=True)
class StepResult:
    ok: bool
    label: str
    detail: str


def _validated_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("BASE_URL must be an absolute http:// or https:// URL")
    return base_url.rstrip("/")


def _aws_secret(secret_id: str, region: str) -> str:
    result = subprocess.run(
        [
            "aws",
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            secret_id,
            "--region",
            region,
            "--query",
            "SecretString",
            "--output",
            "text",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _primary_edge_token_secret() -> str:
    if secret_id := os.environ.get("PRIMARY_EDGE_TOKEN_SECRET"):
        return secret_id
    if stack_name := os.environ.get("STACK_NAME"):
        return f"{stack_name}/edge-token"
    raise ValueError(
        "Set PRIMARY_EDGE_TOKEN_SECRET or STACK_NAME before reading the primary edge token"
    )


def _token() -> str:
    token = os.environ.get("TOKEN") or os.environ.get("AUTH_TOKEN")
    if token:
        return token
    return _aws_secret(
        _primary_edge_token_secret(), os.environ.get("AWS_REGION", "eu-central-1")
    )


def _primary_edge_hostname_label() -> str:
    if hostname_label := os.environ.get("PRIMARY_EDGE_HOSTNAME_LABEL"):
        return hostname_label
    return workload_hostname_label(primary_edge_service_workload())


def _base_url() -> str:
    if base_url := os.environ.get("PRIMARY_EDGE_BASE_URL") or os.environ.get(
        "BASE_URL"
    ):
        return _validated_base_url(base_url)
    if root_domain := os.environ.get("ROOT_DOMAIN"):
        return _validated_base_url(
            f"https://{_primary_edge_hostname_label()}.{root_domain}"
        )
    raise ValueError(
        "Set PRIMARY_EDGE_BASE_URL, BASE_URL, or ROOT_DOMAIN before generating cloud traffic"
    )


def _check_response(
    response: httpx.Response,
    *,
    label: str,
    expected_status: int,
) -> StepResult:
    request_id = response.headers.get("x-request-id", "")
    return StepResult(
        response.status_code == expected_status,
        label,
        f"status={response.status_code} expected={expected_status} request_id={request_id}",
    )


def _print_result(result: StepResult) -> None:
    prefix = "OK" if result.ok else "FAIL"
    stream = sys.stdout if result.ok else sys.stderr
    print(f"{prefix}: {result.label}: {result.detail}", file=stream)


def _metrics_include_observability_series(metrics: str) -> StepResult:
    required = [
        "http_requests_total",
        "http_request_duration_seconds",
    ]
    missing = [name for name in required if name not in metrics]
    return StepResult(
        not missing,
        "GET /metrics",
        f"required_missing={missing}",
    )


def _create_order_payload(customer_id: int, index: int) -> dict[str, str | int]:
    amount = Decimal("10.00") + Decimal(index)
    return {
        "customer_id": customer_id,
        "total_amount": f"{amount:.2f}",
        "billing_email": f"observability-smoke-{uuid.uuid4().hex[:12]}@example.com",
    }


def _candidate_customer_ids() -> list[int]:
    configured = os.environ.get("CUSTOMER_ID_CANDIDATES")
    if configured:
        candidates = [item.strip() for item in configured.split(",") if item.strip()]
        return [int(item) for item in candidates]
    return list(range(1, 201))


def _resolve_customer_id(client: httpx.Client) -> tuple[int | None, StepResult]:
    configured = os.environ.get("CUSTOMER_ID")
    candidates = (
        [int(configured)] if configured is not None else _candidate_customer_ids()
    )
    if not candidates:
        return None, StepResult(False, "resolve customer", "no candidate customer ids")

    checked: list[int] = []
    for candidate in candidates:
        checked.append(candidate)
        response = client.get(f"/customers/{candidate}")
        if response.status_code == 200:
            return candidate, _check_response(
                response,
                label=f"GET /customers/{candidate}",
                expected_status=200,
            )

    return None, StepResult(
        False,
        "resolve customer",
        f"no existing customer found in candidates={checked}; run make seed or set CUSTOMER_ID",
    )


def run() -> list[StepResult]:
    base_url = _base_url()
    order_count = int(os.environ.get("ORDER_COUNT", "3"))
    if order_count < 1 or order_count > 20:
        raise ValueError("ORDER_COUNT must be between 1 and 20")

    headers = {
        "Authorization": f"Bearer {_token()}",
        "X-Request-ID": f"observability-smoke-{uuid.uuid4().hex}",
    }
    results: list[StepResult] = []
    created_order_ids: list[int] = []

    with httpx.Client(base_url=base_url, headers=headers, timeout=20.0) as client:
        for path in ["/ready", "/admin/read-mode", "/admin/write-mode"]:
            response = client.get(path)
            results.append(
                _check_response(response, label=f"GET {path}", expected_status=200)
            )

        customer_id, customer_result = _resolve_customer_id(client)
        results.append(customer_result)

        if customer_id is not None:
            for index in range(order_count):
                idempotency_key = f"observability-smoke-{uuid.uuid4().hex}"
                response = client.post(
                    "/orders",
                    json=_create_order_payload(customer_id, index),
                    headers={"Idempotency-Key": idempotency_key},
                )
                results.append(
                    _check_response(response, label="POST /orders", expected_status=201)
                )
                if response.status_code == 201:
                    payload = response.json()
                    order_id = payload.get("id")
                    if isinstance(order_id, int):
                        created_order_ids.append(order_id)
        else:
            results.append(
                StepResult(
                    False,
                    "POST /orders",
                    "skipped because no existing customer was found",
                )
            )

        for order_id in created_order_ids:
            response = client.get(f"/orders/{order_id}")
            results.append(
                _check_response(
                    response,
                    label=f"GET /orders/{order_id}",
                    expected_status=200,
                )
            )

        response = client.get("/orders/999999999")
        results.append(
            _check_response(
                response,
                label="GET /orders/999999999",
                expected_status=404,
            )
        )

        time.sleep(1)
        response = client.get("/metrics")
        results.append(
            _check_response(response, label="GET /metrics", expected_status=200)
        )
        if response.status_code == 200:
            results.append(_metrics_include_observability_series(response.text))

    results.append(
        StepResult(
            bool(created_order_ids),
            "created order ids",
            json.dumps(created_order_ids),
        )
    )
    return results


def main() -> int:
    try:
        results = run()
    except (httpx.HTTPError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: observability cloud traffic failed: {exc}", file=sys.stderr)
        return 1

    for result in results:
        _print_result(result)

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
