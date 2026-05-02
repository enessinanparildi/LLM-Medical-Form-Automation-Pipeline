"""POST /populate endpoint."""

import base64


def test_populate_returns_pdf(
    fastapi_client,
    schema_fixture: dict,
    llm_response_fixture: dict,
    fillable_pdf_bytes: bytes,
) -> None:
    payload = {
        "schema": schema_fixture,
        "answers": llm_response_fixture,
        "fillable_pdf_b64": base64.b64encode(fillable_pdf_bytes).decode(),
    }
    r = fastapi_client.post("/populate", json=payload)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_populate_rejects_unknown_keys(
    fastapi_client,
    schema_fixture: dict,
    fillable_pdf_bytes: bytes,
) -> None:
    payload = {
        "schema": schema_fixture,
        "answers": {"not_a_real_field": {"value": "x"}},
        "fillable_pdf_b64": base64.b64encode(fillable_pdf_bytes).decode(),
    }
    r = fastapi_client.post("/populate", json=payload)
    assert r.status_code == 400


def test_populate_rejects_invalid_b64(
    fastapi_client,
    schema_fixture: dict,
    llm_response_fixture: dict,
) -> None:
    payload = {
        "schema": schema_fixture,
        "answers": llm_response_fixture,
        "fillable_pdf_b64": "$$not-valid-base64$$",
    }
    r = fastapi_client.post("/populate", json=payload)
    assert r.status_code == 400
