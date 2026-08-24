from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root_returns_metadata():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
    assert "pod" in body


def test_healthz():
    assert client.get("/healthz").status_code == 200


def test_readiness_toggle():
    assert client.get("/readyz").status_code == 200
    client.post("/toggle-ready")
    assert client.get("/readyz").status_code == 503
    client.post("/toggle-ready")
    assert client.get("/readyz").status_code == 200


def test_slow_respects_limit():
    r = client.get("/slow?ms=10")
    assert r.status_code == 200
    assert r.json()["slept_ms"] == 10


def test_order_ok_and_fail():
    assert client.post("/order").status_code == 200
    assert client.post("/order?fail=true").status_code == 500


def test_metrics_exposes_counter():
    client.get("/")
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "app_info" in body
