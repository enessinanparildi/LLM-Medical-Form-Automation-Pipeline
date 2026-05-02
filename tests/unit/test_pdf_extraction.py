"""Schema extraction from a real fillable PDF fixture."""

from io import BytesIO

from medical_form_automation.pdf_extraction import extract_schema


def test_extract_schema_from_fillable_pdf(fillable_pdf_bytes: bytes) -> None:
    schema = extract_schema(BytesIO(fillable_pdf_bytes))
    assert isinstance(schema, dict)
    assert len(schema) > 0


def test_schema_entry_shape(fillable_pdf_bytes: bytes) -> None:
    schema = extract_schema(BytesIO(fillable_pdf_bytes))
    sample = next(iter(schema.values()))
    assert "type" in sample
    assert "pdf_field_name" in sample
    assert sample["type"] in ("text", "checkbox")


def test_checkbox_fields_have_options(fillable_pdf_bytes: bytes) -> None:
    schema = extract_schema(BytesIO(fillable_pdf_bytes))
    checkbox_entries = [v for v in schema.values() if v["type"] == "checkbox"]
    if checkbox_entries:
        for cb in checkbox_entries:
            assert "checkbox_opts" in cb
            assert isinstance(cb["checkbox_opts"], list)
