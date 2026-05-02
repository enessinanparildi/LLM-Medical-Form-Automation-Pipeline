# Medical Form Automation Pipeline

Production-ready Python service that uses an LLM to extract patient data from unstructured medical documents (lab PDFs, SOAP notes, demographics JSON) and populate fillable PDF forms — exposed as a FastAPI service, containerized, CI'd, and tested. **97.96% field-level accuracy** on the included benchmark.

---

## Tech Stack

| Layer | Tools |
|---|---|
| **Language** | Python 3.11 |
| **API** | FastAPI · Uvicorn · Pydantic v2 |
| **LLM / parsing** | Google Gemini 3.0 Flash (via `llama-index-llms-google-genai`) · LlamaParse |
| **PDF** | `pypdf` (form schema extraction + AcroForm population) |
| **Validation** | `phonenumbers` · `pgeocode` · `python-dateutil` · `usaddress` |
| **Config** | `pydantic-settings` (12-factor env / `.env`) |
| **Logging** | `structlog` (JSON to stdout, request-scoped context) |
| **Testing** | `pytest` · `pytest-cov` · `httpx` TestClient · 79% coverage, 70% gate |
| **Quality** | `ruff` (lint + format) · `mypy` |
| **Container** | Multi-stage Dockerfile, non-root user, healthcheck, Python 3.11 slim |
| **CI** | GitHub Actions: lint · typecheck · test · Docker build smoke test |

---

## What It Does

A 3-stage pipeline that turns unstructured medical paperwork into a populated PDF:

1. **`POST /schema`** — parse a fillable PDF, return its field schema (text fields, checkboxes with options, bounding boxes).
2. **`POST /extract`** — feed three labeled sources (S1 lab PDF, S2 SOAP notes, S3 demographics JSON) plus the schema to Gemini, get back per-field `{value, citations, reasoning, confidence}`. Validates phones / area codes / DOBs and reports errors.
3. **`POST /populate`** — fill the original PDF with extracted answers, return the populated PDF binary.

Stateless server — clients pass `schema` and `answers` JSON between calls.

---

## Production Features

This isn't a notebook — it's structured as a service you could actually deploy.

- **HTTP service.** FastAPI app with three pipeline endpoints, `/healthz` (liveness), `/readyz` (config-validated readiness), structured 4xx/5xx error envelopes, automatic OpenAPI docs at `/docs`.
- **Per-request observability.** Every request gets a UUID `x-request-id` header (echoed if inbound), bound into `structlog` contextvars, logged at request start/end with method, path, status, duration. JSON to stdout — drop straight into CloudWatch / Datadog / Loki.
- **PHI-safe logging policy.** Patient values, demographics, lab text, and SOAP content are never logged — only field counts, durations, and error types. Documented and code-reviewed.
- **Strict configuration.** All secrets and tunables loaded via `pydantic-settings` from env / `.env` — `MFA_GEMINI_API_KEY`, `MFA_LLAMA_PARSE_API_KEY`, model, temperature, log level, etc. `Settings()` raises on missing required fields; `/readyz` returns 503 until they're present.
- **Containerized.** Multi-stage Docker build, non-root runtime user, baked-in `HEALTHCHECK`, ~150 MB final image. Image carries no secrets — all injected at runtime.
- **Tested.** 37 unit tests, all external calls (Gemini, LlamaParse) mocked via fixtures captured from real runs. Round-trip PDF population test reads back the written form to verify field mapping. 79% line coverage, 70% gate enforced in CI. Live integration tests are scaffolded (`@pytest.mark.integration`) for when a CI budget is available.
- **CI on every push.** GitHub Actions runs ruff (lint + format), mypy (typecheck), pytest with coverage gate, and a Docker build that boots the container and curls `/healthz` to confirm it actually serves traffic.
- **Strict request validation.** Pydantic models on every endpoint with explicit error types; `/extract` supports `?strict=true` to upgrade validation warnings to 422.
- **Deterministic field mapping.** Schema-driven: the LLM output is keyed by lowercased PDF field name (`/T`), the populator maps back to the original PDF field name and prefixes checkbox values with `/` to match PDF appearance state syntax. Null answers are skipped — never written as empty strings.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Client (curl / SDK / browser)                              │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────────────┐
│  FastAPI (medical_form_automation/api/)                     │
│  ┌────────────┐  ┌──────────┐  ┌────────────┐               │
│  │ /schema    │  │ /extract │  │ /populate  │               │
│  └─────┬──────┘  └────┬─────┘  └──────┬─────┘               │
│        │              │                │                    │
│        ▼              ▼                ▼                    │
│  ┌──────────────────────────────────────────┐               │
│  │  Core (pdf_extraction, extraction,       │               │
│  │        pdf_populate, data_validation)    │               │
│  └────────────┬─────────────────┬───────────┘               │
└───────────────┼─────────────────┼───────────────────────────┘
                │                 │
       ┌────────▼─────┐  ┌────────▼────────┐
       │  LlamaParse  │  │  Google Gemini  │
       │  (lab PDF →  │  │  3.0 Flash      │
       │   markdown)  │  │  (extraction)   │
       └──────────────┘  └─────────────────┘

Cross-cutting: structlog (JSON, request_id contextvar),
pydantic-settings (env config), pytest (mocked LLM/parser).
```

### Three-Source Citation Model

The prompt is built around three labeled sources that the LLM **must** cite:

| Source | Origin | Best for |
|---|---|---|
| **S1** | Lab result PDF (parsed via LlamaParse) | Provider info, insurance/admin fields |
| **S2** | SOAP notes (plain text) | Diagnoses, medications, vitals |
| **S3** | Patient demographics (JSON) | Name, DOB, address, phone |

Conflict-resolution rule: **S3 > S2 > S1**. Every non-null extraction must carry a `citations` array with `{source, quote}` — the model is forced to ground answers in source text.

---

## Quick Start

### Run the API locally

```bash
cp .env.example .env                                  # add your Gemini + LlamaParse keys
pip install -e ".[dev]"
uvicorn medical_form_automation.api.main:app --reload --port 8000
```

```bash
# 1. Get the schema for a fillable PDF
curl -F file=@data/form_fillable.pdf http://localhost:8000/schema > schema.json

# 2. Run extraction (server runs LlamaParse on the lab PDF)
jq -n --argjson schema "$(cat schema.json)" \
      --arg     soap   "$(cat data/soap_notes.txt)" \
      --argjson demo   "$(cat data/demographics.json)" \
      --arg     labb64 "$(base64 -w0 data/lab_result.pdf)" \
      '{schema: $schema, soap_notes: $soap, demographics: $demo, lab_result_pdf_b64: $labb64}' \
  | curl -s -H 'Content-Type: application/json' \
         -d @- http://localhost:8000/extract > extracted.json

# 3. Populate
jq -n --argjson schema  "$(cat schema.json)" \
      --argjson answers "$(jq .answers extracted.json)" \
      --arg     formb64 "$(base64 -w0 data/form_fillable.pdf)" \
      '{schema: $schema, answers: $answers, fillable_pdf_b64: $formb64}' \
  | curl -s -H 'Content-Type: application/json' \
         -d @- http://localhost:8000/populate > populated.pdf
```

OpenAPI docs at `http://localhost:8000/docs`.

### Run via Docker

```bash
docker build -t medical-form-automation .
docker run --rm -p 8000:8000 \
  -e MFA_GEMINI_API_KEY=$GEMINI_KEY \
  -e MFA_LLAMA_PARSE_API_KEY=$LLAMAPARSE_KEY \
  medical-form-automation
```

### Run as CLI (no API)

Console scripts installed via `pip install -e .`:

```bash
extract-schema       # ./data/form_fillable.pdf      → ./output/schema.json
extract-data         # ./data + schema.json          → ./output/answers.json (LIVE LLM)
populate-pdf         # schema + answers              → ./output/pdf_populated.pdf
evaluate-soap        # SOAP-only evaluation suite
```

---

## Project Layout

```
medical_form_automation/        ← installable package
├── config.py                   ← pydantic-settings (env: MFA_*)
├── logging.py                  ← structlog setup, request_id contextvar
├── pdf_extraction.py           ← parse fillable PDF → schema dict
├── extraction.py               ← LLM call across S1/S2/S3
├── pdf_populate.py             ← schema + answers → populated PDF bytes
├── data_validation.py          ← phone/area-code/DOB validators
├── utils.py                    ← Gemini factory, ground-truth comparison
└── api/                        ← FastAPI app
    ├── main.py                 ← app factory + middleware + exception handlers
    ├── routes.py               ← /schema, /extract, /populate, /healthz, /readyz
    ├── schemas.py              ← Pydantic request/response models
    └── deps.py                 ← Settings DI

tests/
├── conftest.py                 ← mock_gemini, mock_llamaparse, fastapi_client fixtures
├── fixtures/                   ← captured schema, parsed lab text, LLM response
└── unit/                       ← 37 tests, all external calls mocked

experiments/
└── ocr_experiment.py           ← preserved reference, not in installed package

.github/workflows/ci.yml        ← lint · typecheck · test · docker build smoke
Dockerfile                      ← multi-stage, non-root, healthcheck
.env.example                    ← required + optional config
```

---

## Configuration

Twelve-factor: every knob is an env var (also accepted via `.env`):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `MFA_GEMINI_API_KEY` | yes | — | Google Gemini API key |
| `MFA_LLAMA_PARSE_API_KEY` | yes | — | LlamaParse API key |
| `MFA_GEMINI_MODEL` | no | `models/gemini-3.0-flash` | Override the LLM model |
| `MFA_GEMINI_TEMPERATURE` | no | `0.1` | Lower = more deterministic |
| `MFA_LOG_LEVEL` | no | `INFO` | Standard log levels |
| `MFA_LOG_JSON` | no | `true` | `false` = pretty colored output for dev |
| `MFA_REQUEST_TIMEOUT_S` | no | `60` | Reserved for upstream call timeouts |

`/readyz` returns 503 until both required keys are present.

---

## Testing

```bash
pytest tests/unit                # 37 tests, ~9s, 79% coverage, 70% gate
pytest tests/unit --no-cov       # skip coverage gate
ruff check . && ruff format --check .
mypy medical_form_automation
```

Test posture: **mocked-only** by default. `tests/conftest.py` patches `get_llamaindex_gemini` and `LlamaParse` to return captured fixture data — fast, deterministic, free in CI. Live integration tests are scaffolded behind `@pytest.mark.integration` for when an API budget is available.

What's tested:
- Schema extraction from a real fillable PDF fixture
- Phone, area-code, and DOB validators (positive + negative cases)
- LLM prompt assembly (assert all sources + field list in the rendered prompt)
- Round-trip PDF population (write, re-parse, assert fields present)
- All four API endpoints — happy path, edge cases, error envelopes, request-ID header propagation
- Configuration validation (raises on missing secrets, caching, env-var precedence)

---

## CI/CD

`.github/workflows/ci.yml` runs four jobs in parallel on every push and PR:

| Job | What it does |
|---|---|
| **lint** | `ruff check` + `ruff format --check` |
| **typecheck** | `mypy medical_form_automation` |
| **test** | `pytest tests/unit` with the 70% coverage gate |
| **docker-build** | Builds the image, runs the container, polls `/healthz` until 200 |

No deploy step in this repo — deployment infrastructure is intended to live separately (e.g. AWS ECS via Pulumi).

---

## Evaluation

### Main pipeline — full-form extraction

**97.96% field-level accuracy** (48/49) against the included ground-truth test patient.

| Field group | Accuracy |
|---|---|
| Demographics (10 fields) | 10/10 — 100% |
| Medications (15 fields) | 15/15 — 100% |
| Dates (12 fields) | 12/12 — 100% |
| Diagnoses (4 fields) | 4/4 — 100% |
| Null-correctly fields (8 fields) | 8/8 — 100% |
| Checkbox fields (5 fields) | 4/5 — 80% |
| **Total** | **48/49 — 97.96%** |

The single miss is a checkbox field where the source text said "Specialist" but the exact PDF option was "Consulting Specialist" — a fuzzy-match gap, not a hallucination. Documented as a known issue with a clear fix (semantic similarity over the option list).

### SOAP-only structured extraction (separate eval)

| Field | Accuracy |
|---|---|
| `patient_age` | 100% |
| `visit_date` | 100% |
| `medications` | 86.7% |
| `chief_complaint` | 33.3% |
| `diagnosis` | 13.3% |

- Formatting error rate: **0%** — prompt instructions are reliably followed
- Hallucination rate: **27.3%** — validates the strict citation requirement in the production prompt

---

## Key Design Decisions

**LLM-first over rule-based NLP.** Medical language is too variable for regex (`BP` / `B/P` / `blood pressure`). LLMs handle this fuzzy matching natively.

**Citations as a hard constraint.** Every non-null extraction carries `{source, quote}`. Forces grounding, makes failures debuggable, surfaces auditability for free.

**Validation is reporting, not raising.** `run_validations()` returns a list of errors; the API surfaces them in the response and only escalates to 422 when `?strict=true`. Lets the client choose whether to populate anyway with a low-confidence value.

**Text-completion + regex JSON parse, not constrained-decoding.** Pydantic structured output via `as_structured_llm` failed on Gemini ("schema produces a constraint that has too many states") because of the ~50 fields × nested citation objects. The text-completion path is documented as the working path; constrained generation is preserved in the SOAP-only eval where the schema is small.

**Schema-driven, not example-driven.** The form schema is parsed from the PDF at request time, so the system works for any fillable PDF — no per-form code changes needed.

**OCR is intentionally out of scope.** Modern fillable PDFs carry structured AcroForm metadata; OCR experiments (`experiments/ocr_experiment.py`) showed layout models added complexity without improving accuracy. Kept around as a reference; not in the installed package.

---

## Prompt Engineering Strategy

The extraction prompt has six explicit rule categories:

1. **Field-spec echo** — the model copies the exact line from `FIELDS TO FILL` for each output, so we can verify it understood the schema.
2. **Coverage** — fill what's there, set `null` for what isn't. No guessing.
3. **Conflict resolution** — `S3 > S2 > S1` priority baked into the prompt.
4. **Format normalization** — dates as `YYYY-MM-DD`, phones split into `(3, 3, 4)`, height/weight numeric.
5. **Checkbox handling** — return the exact option text, not synonyms.
6. **Evidence requirement** — every non-null answer carries a quote citation.

A confidence calibration scale (0.90–1.00 explicit match → 0.00 null) is included to enable human-in-the-loop review prioritization.

---

## Known Limitations / Future Work

- **Checkbox fuzzy matching** — fixable with semantic similarity over option strings (the one accuracy miss).
- **Structured output (Pydantic) on Gemini** — blocked by constraint complexity at ~50 fields; would need GPT-4 function calling or schema chunking.
- **Live integration test suite** — marker is registered, tests are not written. Deferred until CI has API budget.
- **Multi-page forms** — schema extraction handles them but the prompt is sized for single-page; would need chunking.
- **OCR fallback for scanned PDFs** — preserved in `experiments/` but out of scope.
- **Auth on the API** — none today; assumes private network or upstream auth proxy.
- **Async job queue** — not needed at current latency (~5s per extraction); add Redis + worker if request volume grows.

---

## License

MIT
