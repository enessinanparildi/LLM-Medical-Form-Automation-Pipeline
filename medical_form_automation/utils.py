"""Shared helpers: ground-truth comparison, schema flattening, Gemini factory."""

import json
from pathlib import Path
from typing import Any

from llama_index.llms.google_genai import GoogleGenAI

from medical_form_automation.config import Settings, get_settings


_SAFE_SETTINGS = [
    {"category": "HARM_CATEGORY_DANGEROUS", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]


def get_llamaindex_gemini(settings: Settings | None = None) -> GoogleGenAI:
    cfg = settings or get_settings()
    return GoogleGenAI(
        model_name=cfg.gemini_model,
        api_key=cfg.gemini_api_key.get_secret_value(),
        temperature=cfg.gemini_temperature,
        safety_settings=_SAFE_SETTINGS,
    )


def field_data_from_schema(schema: dict[str, Any]) -> tuple[str, list[str]]:
    """Render a schema dict as the bullet-list FIELDS TO FILL prompt block."""
    lines: list[str] = []
    for field_name, fdata in schema.items():
        if fdata.get("type") == "checkbox":
            options = ", ".join(fdata.get("checkbox_opts", []))
            lines.append(f"• {field_name} , {fdata.get('label')} (Options: {options})")
        else:
            lines.append(f"• {field_name} : {fdata.get('label')}")
    return "\n".join(lines), lines


def get_field_data(schema_path: str | Path = "./output/schema.json") -> tuple[str, list[str], dict[str, Any]]:
    """CLI helper: load schema.json from disk and return (text, lines, raw)."""
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    text, lines = field_data_from_schema(schema)
    return text, lines, schema


def compare_with_ground_truth(answers: dict[str, Any]) -> dict[str, Any]:
    """Compare an answers dict to the hardcoded test-patient ground truth."""
    ground_truth: dict[str, Any] = {
        "first name": "Peter Julius Fern",
        "areacode": "613",
        "phonea": "656",
        "phoneb": "5890",
        "areacode1": "647",
        "phonea1": "666",
        "phoneb1": "8888",
        "address": "45 Maple Ave, Toronto, ON, K7L 3V8",
        "employer name": None,
        "contract": "9696178816",
        "cert": None,
        "date_of_birth_d": "15",
        "date_of_birth_m": "04",
        "date_of_birth_y": "1960",
        "date_last_d": None,
        "date_last_m": None,
        "date_last_y": None,
        "date_return_d": None,
        "date_return_m": None,
        "date_return_y": None,
        "medication1": "Aspirin",
        "medication2": "Metoprolol",
        "medication3": "Nitroglycerin",
        "medication4": None,
        "medication5": None,
        "dose1": "81",
        "dose2": "25",
        "dose3": "0.4",
        "dose4": None,
        "dose5": None,
        "often1": "once a day",
        "often2": "twice daily",
        "often3": "as needed",
        "often4": None,
        "often5": None,
        "height": None,
        "weight": None,
        "hand": None,
        "company_name": None,
        "doctor": "Consulting Specialist",
        "doctor_other": None,
        "diagnosis_primary1": "stable angina",
        "diagnosis_primary2": "Hypertension",
        "diagnosis_secondary1": "GERD",
        "diagnosis_secondary2": "Hyperlipidemia",
        "date_childbirth_d": None,
        "date_childbirth_m": None,
        "date_childbirth_y": None,
        "delivery": None,
    }

    def normalize(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower()
        return str(value).strip().lower()

    correct = 0
    incorrect = 0
    correct_fields: list[str] = []
    incorrect_fields: list[dict[str, Any]] = []
    missing_fields: list[str] = []

    for key, expected in ground_truth.items():
        if key not in answers:
            missing_fields.append(key)
            incorrect += 1
            continue

        entry = answers[key]
        actual = entry.get("value") if isinstance(entry, dict) else entry

        if normalize(expected) == normalize(actual):
            correct += 1
            correct_fields.append(key)
        else:
            incorrect += 1
            incorrect_fields.append({"field": key, "expected": expected, "got": actual})

    total = len(ground_truth)
    accuracy = round((correct / total) * 100, 2) if total > 0 else 0.0
    return {
        "accuracy": accuracy,
        "correct_count": correct,
        "incorrect_count": incorrect,
        "total_fields": total,
        "correct_fields": correct_fields,
        "incorrect_fields": incorrect_fields,
        "missing_fields": missing_fields,
    }
