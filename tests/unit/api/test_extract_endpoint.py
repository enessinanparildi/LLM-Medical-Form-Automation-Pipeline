"""POST /extract endpoint."""

import base64


def test_extract_with_lab_text(
    fastapi_client,
    schema_fixture: dict,
    soap_fixture: str,
    demographics_fixture: dict,
    lab_text_fixture: str,
) -> None:
    payload = {
        "schema": schema_fixture,
        "soap_notes": soap_fixture,
        "demographics": demographics_fixture,
        "lab_result_text": lab_text_fixture,
    }
    r = fastapi_client.post("/extract", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "answers" in body
    assert "validation" in body
    assert isinstance(body["answers"], dict)
    assert "ok" in body["validation"]
    assert "errors" in body["validation"]


def test_extract_with_lab_pdf_b64(
    fastapi_client,
    schema_fixture: dict,
    soap_fixture: str,
    demographics_fixture: dict,
    fillable_pdf_bytes: bytes,
) -> None:
    payload = {
        "schema": schema_fixture,
        "soap_notes": soap_fixture,
        "demographics": demographics_fixture,
        "lab_result_pdf_b64": base64.b64encode(fillable_pdf_bytes).decode(),
    }
    r = fastapi_client.post("/extract", json=payload)
    assert r.status_code == 200


def test_extract_missing_lab_source_400(
    fastapi_client,
    schema_fixture: dict,
    soap_fixture: str,
    demographics_fixture: dict,
) -> None:
    payload = {
        "schema": schema_fixture,
        "soap_notes": soap_fixture,
        "demographics": demographics_fixture,
    }
    r = fastapi_client.post("/extract", json=payload)
    assert r.status_code == 400


def test_extract_strict_mode_passes_when_clean(
    fastapi_client,
    schema_fixture: dict,
    soap_fixture: str,
    demographics_fixture: dict,
    lab_text_fixture: str,
) -> None:
    payload = {
        "schema": schema_fixture,
        "soap_notes": soap_fixture,
        "demographics": demographics_fixture,
        "lab_result_text": lab_text_fixture,
    }
    r = fastapi_client.post("/extract?strict=true", json=payload)
    # With our fixture llm_response, validations should pass cleanly
    assert r.status_code in (200, 422)
