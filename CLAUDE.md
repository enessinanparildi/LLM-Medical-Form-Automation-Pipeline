# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

LLM-based pipeline that extracts patient data from unstructured medical documents (lab PDFs, SOAP notes, demographics JSON) and populates fillable PDF forms. Uses Gemini 3.0 Flash via `llama-index-llms-google-genai` and LlamaParse for PDF→markdown. Exposed as a 3-stage FastAPI service and as four console-script CLIs.

## Layout

- `medical_form_automation/` — installable package
  - `config.py` — `pydantic-settings` Settings, env prefix `MFA_`
  - `logging.py` — structlog setup; PHI policy: never log values, demographics, lab text, or SOAP
  - `pdf_extraction.py` — `extract_schema(pdf_source)` parses fillable PDF → schema dict
  - `extraction.py` — `parse_lab_pdf(...)`, `run_extraction(...)`, `extract_json_object(...)`
  - `pdf_populate.py` — `build_pdf_field_values(...)`, `populate_pdf(...)` returns PDF bytes in memory
  - `data_validation.py` — `run_validations(answers)` returns list of errors (does NOT raise)
  - `utils.py` — `get_llamaindex_gemini(settings)`, `field_data_from_schema(...)`, `compare_with_ground_truth(...)`
  - `api/` — FastAPI app: `main.py` factory + middleware, `routes.py`, `schemas.py`, `deps.py`
- `tests/unit/` — mocked-LLM unit tests; `tests/fixtures/` holds captured fixture data
- `experiments/ocr_experiment.py` — preserved reference, NOT installed/imported anywhere
- `data/` — demo inputs (committed)
- `output/` — scratch outputs (gitignored)

## Commands

```bash
pip install -e ".[dev]"

# Run the API locally
uvicorn medical_form_automation.api.main:app --reload --port 8000

# CLI scripts (installed from pyproject [project.scripts])
extract-schema         # ./data/form_fillable.pdf → ./output/schema.json
extract-data           # ./data + ./output/schema.json → ./output/answers.json (LIVE LLM call)
populate-pdf           # ./output/schema.json + answers.json → ./output/pdf_populated.pdf
evaluate-soap          # SOAP eval against data/soap_training_data.json (LIVE LLM call)

# Tests / lint / typecheck (run from repo root)
pytest tests/unit                  # 79% coverage, all mocked
pytest tests/unit --no-cov         # skip the 70% gate
ruff check . && ruff format --check .
mypy medical_form_automation
```

## Required env (see `.env.example`)

Both secrets are mandatory — `Settings()` raises `ValidationError` if either is missing.
- `MFA_GEMINI_API_KEY`
- `MFA_LLAMA_PARSE_API_KEY`

`Settings` is cached via `lru_cache`; call `get_settings.cache_clear()` between tests if you change env vars (the autouse fixture in `tests/conftest.py` does this).

## API contract

All three pipeline endpoints are sync. Stateless server — clients pass `schema` and `answers` JSON between calls.

- `POST /schema` (multipart `file=<fillable PDF>`) → schema JSON
- `POST /extract` (JSON `{schema, soap_notes, demographics, lab_result_text | lab_result_pdf_b64}`, optional `?strict=true`) → `{answers, validation}`. With `strict=true`, validation errors return 422.
- `POST /populate` (JSON `{schema, answers, fillable_pdf_b64}`) → `application/pdf` body
- `GET /healthz` always 200; `GET /readyz` 503 if either secret is missing

Every response includes an `x-request-id` header (generated server-side or echoed from inbound `x-request-id`). Errors come back as `{"detail": ..., "request_id": ...}`.

## Architecture notes worth knowing

### Three-source citation model
The prompt is built around three labeled sources the LLM must cite:
- **S1** = lab result PDF (LlamaParse → markdown). `extraction.preprocess_lab_text` expands `Dr` → `Doctor`, `MD` → `Medical Doctor`, strips hyphens — these substitutions affect downstream extraction.
- **S2** = SOAP notes (plain text)
- **S3** = patient demographics (JSON)

Conflict resolution rule baked into the prompt: **S3 > S2 > S1**. An alternative per-field priority map exists in the codebase but is not wired into the prompt — it's documented as an alternative.

### Schema-driven extraction
`pdf_extraction.extract_schema` keys the schema by **lowercased PDF field name** (`/T`). Each entry has `label` (`/TU`), `type` (`text` or `checkbox`), `bbox`, `pdf_field_name` (original `/T`), and for checkboxes `checkbox_opts` extracted from `/AP/N`.

The LLM output is keyed by the same lowercased `/T` names. `pdf_populate.build_pdf_field_values` maps each key back to `pdf_field_name` and prefixes checkbox values with `/` to match PDF appearance state syntax. Null values are skipped, not written as empty strings.

### Validation is reporting, not raising
`data_validation.run_validations(answers)` returns a list of errors. Callers decide what to do — the API surfaces them via `validation.errors` in the response and only escalates to 422 when `?strict=true`. (The pre-restructure code raised on first error; that behavior is gone.)

### Address validation is intentionally disabled
`usaddress` failed on the test address. The hook is still there in the validation helpers but `run_validations` doesn't call it. Leave it disabled unless you swap parsers.

### Structured-output (Pydantic) path is intentionally NOT used here
The prompt-engineering doc and `soap_eval.py` use `llm.as_structured_llm(...)`, but the main extraction stays text-completion + `extract_json_object()` (regex `{.*}` + `json.loads`) because Gemini's structured-output constraint solver chokes on the ~50-field schema with nested citations.

### OCR module is preserved but out-of-scope
`experiments/ocr_experiment.py` runs heavy `layoutparser`/PaddleDetection/Tesseract code at import time. It's not in the installed package, has no entry point, no tests reference it. Keep it that way unless the OCR scope changes.

## Testing notes

- Tests run **mocked-only** by default — no live Gemini or LlamaParse calls. CI runs unit tests on every PR.
- `tests/conftest.py::mock_gemini` patches `medical_form_automation.extraction.get_llamaindex_gemini`. `mock_llamaparse` patches `medical_form_automation.extraction.LlamaParse`. Both are non-autouse — pull them in by name in tests that need them.
- Live integration tests are deferred (would be `pytest -m integration`); the marker is registered in `pyproject.toml` but no integration tests exist yet.
- Coverage gate is 70% in `pyproject.toml` — the `pytest` command in CI enforces it.
- `pgeocode` does a one-time download on first import. Local test runs after the cache warms up are ~10s; cold runs (e.g. fresh CI) can take minutes. Don't be alarmed by the first run.

## Ground truth

`utils.compare_with_ground_truth` hardcodes the expected values for the test patient ("Peter Julius Fern", DOB 1960-04-15). It's not loaded from a file — editing the test case means editing the function. Reported accuracy: 48/49 fields (97.96%); the single miss is the `doctor` checkbox ("Consulting Specialist") due to fuzzy-match gaps between source text and exact checkbox option strings.
