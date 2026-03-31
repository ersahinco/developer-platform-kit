"""test_api.py — HTTP layer integration tests. Req 5.4, 10.1, 10.3"""

import pytest
from conftest import post_order


@pytest.mark.require_phase("legacy", "dual", "switch")
def test_create_and_read_order(http_client):
    """Round-trip: POST then GET returns billing_email. Req 10.1"""
    order_id = post_order(http_client, billing_email="test@example.com")
    resp = http_client.get(f"/orders/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["billing_email"] == "test@example.com"


def test_order_not_found(http_client):
    assert http_client.get("/orders/999999999").status_code == 404


def test_invalid_read_mode(http_client):
    assert http_client.post("/admin/read-mode", json={"mode": "invalid_mode"}).status_code == 400
