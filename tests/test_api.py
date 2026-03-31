"""
test_api.py — Integration tests for the FastAPI HTTP layer.

Validates: Requirements 5.4, 10.1, 10.3
"""


def test_create_and_read_order(http_client):
    """POST an order with billing_email, GET it back, assert email matches. Req 10.1"""
    resp = http_client.post("/orders", json={
        "customer_id": 1,
        "total_amount": 99.99,
        "status": "SUBMITTED",
        "billing_email": "test@example.com",
    })
    assert resp.status_code == 201, resp.text
    order_id = resp.json()["id"]

    get_resp = http_client.get(f"/orders/{order_id}")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["billing_email"] == "test@example.com"


def test_order_not_found(http_client):
    """GET a non-existent order_id returns HTTP 404."""
    assert http_client.get("/orders/999999999").status_code == 404


def test_invalid_read_mode(http_client):
    """POST /admin/read-mode with an invalid mode returns HTTP 400. Req 5.4"""
    assert http_client.post("/admin/read-mode", json={"mode": "invalid_mode"}).status_code == 400
