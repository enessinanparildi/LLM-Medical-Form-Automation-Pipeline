"""Health endpoints."""


def test_healthz_ok(fastapi_client) -> None:
    r = fastapi_client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "version" in r.json()


def test_readyz_ok_when_secrets_present(fastapi_client) -> None:
    r = fastapi_client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
