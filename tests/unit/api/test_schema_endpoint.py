"""POST /schema endpoint."""

import io


def test_schema_endpoint_parses_pdf(fastapi_client, fillable_pdf_bytes: bytes) -> None:
    files = {"file": ("form.pdf", io.BytesIO(fillable_pdf_bytes), "application/pdf")}
    r = fastapi_client.post("/schema", files=files)
    assert r.status_code == 200
    schema = r.json()
    assert isinstance(schema, dict)
    assert len(schema) > 0


def test_schema_endpoint_rejects_empty_file(fastapi_client) -> None:
    files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    r = fastapi_client.post("/schema", files=files)
    assert r.status_code == 400


def test_schema_endpoint_rejects_garbage(fastapi_client) -> None:
    files = {"file": ("garbage.pdf", io.BytesIO(b"not a pdf at all"), "application/pdf")}
    r = fastapi_client.post("/schema", files=files)
    assert r.status_code == 400


def test_request_id_header_returned(fastapi_client) -> None:
    r = fastapi_client.get("/healthz")
    assert "x-request-id" in r.headers
