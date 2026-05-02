"""PDF population: schema-aware mapping and round-trip."""

from io import BytesIO

import pytest
from pypdf import PdfReader

from medical_form_automation.pdf_populate import build_pdf_field_values, populate_pdf


def test_build_field_values_text(schema_fixture: dict) -> None:
    answers = {key: {"value": "X"} for key, spec in schema_fixture.items() if spec["type"] == "text"}
    pdf_values = build_pdf_field_values(schema_fixture, answers)
    assert all(v == "X" for v in pdf_values.values())


def test_build_field_values_checkbox_prefix(schema_fixture: dict) -> None:
    cb_keys = [k for k, v in schema_fixture.items() if v["type"] == "checkbox" and v.get("checkbox_opts")]
    if not cb_keys:
        pytest.skip("Schema has no checkbox fields with options")

    key = cb_keys[0]
    opt = schema_fixture[key]["checkbox_opts"][0]
    answers = {key: {"value": opt}}
    out = build_pdf_field_values(schema_fixture, answers)
    pdf_name = schema_fixture[key]["pdf_field_name"]
    assert out[pdf_name] == "/" + opt


def test_build_field_values_skips_null() -> None:
    schema = {"name1": {"type": "text", "pdf_field_name": "Name1"}}
    answers = {"name1": {"value": None}}
    assert build_pdf_field_values(schema, answers) == {}


def test_build_field_values_unknown_type_raises() -> None:
    schema = {"weird": {"type": "signature", "pdf_field_name": "Weird"}}
    answers = {"weird": {"value": "x"}}
    with pytest.raises(ValueError):
        build_pdf_field_values(schema, answers)


def test_populate_pdf_roundtrip(
    fillable_pdf_bytes: bytes,
    schema_fixture: dict,
    llm_response_fixture: dict,
) -> None:
    populated = populate_pdf(BytesIO(fillable_pdf_bytes), schema_fixture, llm_response_fixture)
    assert populated.startswith(b"%PDF")

    reader = PdfReader(BytesIO(populated))
    fields = reader.get_fields() or {}
    assert len(fields) > 0

    # At least one populated text field should round-trip
    text_keys = [k for k, v in schema_fixture.items() if v["type"] == "text"]
    populated_text_keys = [
        k
        for k in text_keys
        if (entry := llm_response_fixture.get(k))
        and isinstance(entry, dict)
        and entry.get("value") not in (None, "")
    ]
    if populated_text_keys:
        sample_key = populated_text_keys[0]
        pdf_field_name = schema_fixture[sample_key]["pdf_field_name"]
        assert pdf_field_name in fields
