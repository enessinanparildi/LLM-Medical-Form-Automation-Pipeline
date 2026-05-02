"""LLM extraction wiring (Gemini + LlamaParse mocked)."""

import json
from io import BytesIO

from unittest.mock import MagicMock

from medical_form_automation.extraction import (
    extract_json_object,
    parse_lab_pdf,
    preprocess_lab_text,
    run_extraction,
)


def test_preprocess_lab_text_substitutions() -> None:
    src = "Dr Smith, MD - 5mg dr pill"
    out = preprocess_lab_text(src)
    assert "Dr" not in out.replace("Doctor", "")  # all Dr → Doctor
    assert "MD" not in out.replace("Medical Doctor", "")
    assert "-" not in out


def test_extract_json_object_handles_prose_around_json() -> None:
    text = 'noise before {"a": 1, "b": "hi"} noise after'
    assert extract_json_object(text) == {"a": 1, "b": "hi"}


def test_extract_json_object_raises_on_no_json() -> None:
    import pytest

    with pytest.raises(ValueError):
        extract_json_object("nope, no braces here")


def test_run_extraction_calls_llm_with_assembled_prompt(
    mock_gemini: MagicMock,
    schema_fixture: dict,
    soap_fixture: str,
    demographics_fixture: dict,
    lab_text_fixture: str,
    llm_response_fixture: dict,
) -> None:
    answers = run_extraction(
        schema=schema_fixture,
        lab_result_text=lab_text_fixture,
        soap_notes=soap_fixture,
        demographics=demographics_fixture,
    )
    assert answers == llm_response_fixture
    mock_gemini.complete.assert_called_once()
    prompt = mock_gemini.complete.call_args[0][0]
    assert "FIELDS TO FILL" in prompt
    assert "[S1]" in prompt and "[S2]" in prompt and "[S3]" in prompt
    assert lab_text_fixture in prompt
    assert soap_fixture in prompt


def test_parse_lab_pdf_uses_llamaparse_and_preprocesses(
    mock_llamaparse: MagicMock,
    lab_text_fixture: str,
) -> None:
    out = parse_lab_pdf(BytesIO(b"fake-pdf-bytes"))
    # Preprocessor must have run
    assert "Dr " not in out  # any "Dr " was replaced with "Doctor "
    mock_llamaparse.load_data.assert_called_once()
