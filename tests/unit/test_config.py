"""Configuration loading."""

import pytest
from pydantic import ValidationError

from medical_form_automation.config import Settings, get_settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MFA_GEMINI_API_KEY", "g")
    monkeypatch.setenv("MFA_LLAMA_PARSE_API_KEY", "l")
    monkeypatch.setenv("MFA_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MFA_LOG_JSON", "false")

    s = Settings()
    assert s.gemini_api_key.get_secret_value() == "g"
    assert s.llama_parse_api_key.get_secret_value() == "l"
    assert s.log_level == "DEBUG"
    assert s.log_json is False
    assert s.gemini_model == "models/gemini-3.0-flash"


def test_settings_missing_secrets_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MFA_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("MFA_LLAMA_PARSE_API_KEY", raising=False)
    # Prevent reading a project-root .env that would supply these:
    monkeypatch.setenv("PYDANTIC_SETTINGS_DISABLE_DOTENV", "1")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_get_settings_is_cached() -> None:
    a = get_settings()
    b = get_settings()
    assert a is b
