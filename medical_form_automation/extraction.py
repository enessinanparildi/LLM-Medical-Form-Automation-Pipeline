"""LLM extraction across the three sources (S1 lab, S2 SOAP, S3 demographics)."""

import json
import re
import time
from pathlib import Path
from typing import Any, BinaryIO

from llama_index.core import PromptTemplate
from llama_parse import LlamaParse

from medical_form_automation.config import Settings, get_settings
from medical_form_automation.logging import get_logger
from medical_form_automation.utils import field_data_from_schema, get_llamaindex_gemini

log = get_logger(__name__)


_PROMPT_TEMPLATE = (
    "You are an information extraction system.\n"
    "Use ONLY the information in the provided sources. Do NOT guess, infer, or fabricate.\n\n"
    "However, you have a general understanding of how medical bureaucracy and insurance policy works in Canada and the United States.\n\n"
    "For example, in Canada policy number is represented as a healthcard number.\n\n"
    "FIELDS TO FILL:\n"
    "{field_list_str}\n\n"
    "SOURCES (cite these explicitly):\n"
    "[S1] Lab result form (unstructured text):\n"
    "{lab_result_text}\n\n"
    "[S2] SOAP notes (unstructured text):\n"
    "{soap_text}\n\n"
    "[S3] Patient personal data (JSON):\n"
    "{json_data}\n\n"
    "EXTRACTION RULES:\n"
    "0) Field spec echo (required):\n"
    "   - For each output key, set field_spec to the EXACT matching line from FIELDS TO FILL that begins with that key.\n"
    "   - Copy it verbatim (including checkbox options if present).\n"
    "   - If you cannot find a matching line, set field_spec = null.\n"
    "1) Coverage: Fill as many fields as possible. If not explicitly stated, set value = null.\n"
    "2) Conflicts: If sources disagree, prefer S3 > S2 > S1. If still ambiguous, set null.\n"
    "3) Formatting:\n"
    "   - Dates: YYYY-MM-DD when available; otherwise keep partial (YYYY-MM or YYYY) as a string.\n"
    "   - Phone: digits only. If a full phone appears, ignore separators(-), split into areacode (3 digits), first part (3 digits), second part (4 digits) when possible. Always follow the standard phone number format (3 digits - 3 digits - 4 digits)\n"
    "   - Height/weight: keep numeric + unit if present; otherwise numeric only.\n"
    "4) Checkbox fields:\n"
    "   - Return the selected option exactly as listed in the field options.\n"
    "   - If multiple selections are explicitly indicated, return a list of strings.\n"
    "   - If selection is not explicit, return null.\n"
    "5) Evidence requirement:\n"
    "   - Every non-null value MUST include at least one citation with a short supporting quote/snippet.\n\n"
    "OUTPUT (JSON only; no extra text):\n"
    "Return a single JSON object keyed by the field keys. Each field maps to an object with:\n"
    '  - "field_spec": the exact matching line from FIELDS TO FILL for this key (copy verbatim)\n'
    '  - "value": extracted value (string/number/list) or null, this must only the answer phrase without anything else. For example, diagnosis must only be the name of diagnosis.\n'
    '  - "citations": [] if value is null; otherwise a list of { "source": "S1|S2|S3", "quote": "..." }\n'
    '  - "reasoning": brief explanation of how the value was chosen, including conflict resolution if applicable\n'
    '  - "confidence": a number 0.0-1.0 with a brief justification in reasoning (e.g., direct match vs ambiguous)\n\n'
    "Confidence guidance (explain briefly in reasoning):\n"
    "- 0.90-1.00: explicit exact match in a single source (e.g., S3 JSON field or clear statement in notes); increase if corroborated across sources, if the document itself mentions any doubt, lower the confidence.\n"
    "- 0.60-0.89: explicit but requires mild normalization (date/phone split) or clearly implied by nearby context.\n"
    "- 0.30-0.59: weak/partial evidence, competing candidates, or incomplete value.\n"
    "- 0.00: value is null\n\n"
    "Required JSON schema example:\n"
    "{\n"
    '  "first name": {\n'
    '    "field_spec": "first name: Patient First Name",\n'
    '    "value": "John",\n'
    '    "citations": [\n'
    '      {"source": "S2", "quote": "Patient: John Doe"}\n'
    "    ],\n"
    '    "reasoning": "First name appears explicitly in S2.",\n'
    '    "confidence": 0.85\n'
    "  },\n"
    '  "hand": {\n'
    '    "field_spec": "hand: Dominant hand (options: Right, Left)",\n'
    '    "value": "Right",\n'
    '    "citations": [\n'
    '      {"source": "S3", "quote": "\\"dominant_hand\\": \\"Right\\""}\n'
    "    ],\n"
    '    "reasoning": "Dominant hand explicitly stated in S3; checkbox option matches exactly.",\n'
    '    "confidence": 0.95\n'
    "  }\n"
    "}\n"
)


def parse_lab_pdf(pdf_source: str | Path | BinaryIO, settings: Settings | None = None) -> str:
    """Run LlamaParse on a lab result PDF and return preprocessed markdown text."""
    cfg = settings or get_settings()
    parser = LlamaParse(
        api_key=cfg.llama_parse_api_key.get_secret_value(),
        result_type="markdown",
        num_workers=4,
        verbose=False,
        language="en",
    )
    docs = parser.load_data(pdf_source)
    merged = "\n".join(d.text for d in docs)
    return preprocess_lab_text(merged)


def preprocess_lab_text(text: str) -> str:
    text = text.replace("Dr", "Doctor")
    text = text.replace("MD", "Medical Doctor")
    text = text.replace("dr", "Doctor")
    text = text.replace("-", " ")
    return text


def extract_json_object(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(m.group(0))


def run_extraction(
    schema: dict[str, Any],
    lab_result_text: str,
    soap_notes: str,
    demographics: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Send all three sources + the schema to Gemini, return parsed answers."""
    cfg = settings or get_settings()
    field_list_str, _ = field_data_from_schema(schema)
    template = PromptTemplate(_PROMPT_TEMPLATE)
    prompt = template.format(
        field_list_str=field_list_str,
        lab_result_text=lab_result_text,
        soap_text=soap_notes,
        json_data=json.dumps(demographics),
    )

    llm = get_llamaindex_gemini(cfg)
    log.info(
        "llm.extract.start",
        field_count=len(schema),
        model=cfg.gemini_model,
        prompt_chars=len(prompt),
    )
    started = time.perf_counter()
    response = llm.complete(prompt)
    duration_ms = int((time.perf_counter() - started) * 1000)

    answers = extract_json_object(response.text)
    log.info(
        "llm.extract.end",
        duration_ms=duration_ms,
        answer_keys=len(answers),
        schema_keys=len(schema),
    )
    return answers


def main() -> None:
    """CLI entry point — runs the full pipeline against ./data and writes ./output/answers.json."""
    from medical_form_automation.data_validation import run_validations

    schema_path = Path("./output/schema.json")
    answers_path = Path("./output/answers.json")
    answers_path.parent.mkdir(parents=True, exist_ok=True)

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    soap = Path("./data/soap_notes.txt").read_text(encoding="utf-8")
    demographics = json.loads(Path("./data/demographics.json").read_text(encoding="utf-8"))
    lab_text = parse_lab_pdf("./data/lab_result.pdf")

    answers = run_extraction(schema, lab_text, soap, demographics)
    answers_path.write_text(json.dumps(answers, indent=4, ensure_ascii=False), encoding="utf-8")

    errors = run_validations(answers)
    if errors:
        log.warning("validation.errors", error_count=len(errors), fields=[e["field"] for e in errors])
    else:
        log.info("validation.ok", field_count=len(answers))


if __name__ == "__main__":
    main()
