"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide dummy secrets so Settings() never fails during test collection."""
    monkeypatch.setenv("MFA_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("MFA_LLAMA_PARSE_API_KEY", "test-llamaparse-key")
    monkeypatch.setenv("MFA_LOG_JSON", "false")

    # Bust the lru_cache on get_settings between tests
    from medical_form_automation.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def fillable_pdf_bytes() -> bytes:
    return (FIXTURES / "form_fillable.pdf").read_bytes()


@pytest.fixture
def schema_fixture() -> dict[str, Any]:
    return json.loads((FIXTURES / "schema.json").read_text(encoding="utf-8"))


@pytest.fixture
def demographics_fixture() -> dict[str, Any]:
    return json.loads((FIXTURES / "demographics.json").read_text(encoding="utf-8"))


@pytest.fixture
def soap_fixture() -> str:
    return (FIXTURES / "soap_notes.txt").read_text(encoding="utf-8")


@pytest.fixture
def lab_text_fixture() -> str:
    return (FIXTURES / "lab_result_parsed.md").read_text(encoding="utf-8")


@pytest.fixture
def llm_response_fixture() -> dict[str, Any]:
    return json.loads((FIXTURES / "llm_response.json").read_text(encoding="utf-8"))


@pytest.fixture
def mock_gemini(monkeypatch: pytest.MonkeyPatch, llm_response_fixture: dict[str, Any]) -> MagicMock:
    """Patch get_llamaindex_gemini() to return a mock whose .complete() returns fixture JSON."""
    fake_response = MagicMock()
    fake_response.text = json.dumps(llm_response_fixture)

    fake_llm = MagicMock()
    fake_llm.complete.return_value = fake_response

    factory = MagicMock(return_value=fake_llm)
    monkeypatch.setattr("medical_form_automation.extraction.get_llamaindex_gemini", factory)
    return fake_llm


@pytest.fixture
def mock_llamaparse(monkeypatch: pytest.MonkeyPatch, lab_text_fixture: str) -> MagicMock:
    """Patch LlamaParse.load_data to return docs whose .text is the fixture."""
    fake_doc = MagicMock()
    fake_doc.text = lab_text_fixture

    fake_parser = MagicMock()
    fake_parser.load_data.return_value = [fake_doc]

    parser_cls = MagicMock(return_value=fake_parser)
    monkeypatch.setattr("medical_form_automation.extraction.LlamaParse", parser_cls)
    return fake_parser


@pytest.fixture
def fastapi_client(mock_gemini: MagicMock, mock_llamaparse: MagicMock):
    from fastapi.testclient import TestClient

    from medical_form_automation.api.main import create_app

    app = create_app()
    return TestClient(app)
