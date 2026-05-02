"""HTTP routes: /schema, /extract, /populate, /healthz, /readyz."""

import base64
import io
import time
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from medical_form_automation import __version__
from medical_form_automation.api.deps import SettingsDep
from medical_form_automation.api.schemas import (
    ExtractRequest,
    ExtractResponse,
    HealthResponse,
    PopulateRequest,
    ReadinessResponse,
)
from medical_form_automation.data_validation import run_validations
from medical_form_automation.extraction import (
    parse_lab_pdf,
    preprocess_lab_text,
    run_extraction,
)
from medical_form_automation.logging import get_logger
from medical_form_automation.pdf_extraction import extract_schema
from medical_form_automation.pdf_populate import populate_pdf

log = get_logger(__name__)
router = APIRouter()


@router.get("/healthz", response_model=HealthResponse, tags=["health"])
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get("/readyz", response_model=ReadinessResponse, tags=["health"])
def readyz(settings: SettingsDep) -> ReadinessResponse:
    issues: list[str] = []
    if not settings.gemini_api_key.get_secret_value():
        issues.append("missing MFA_GEMINI_API_KEY")
    if not settings.llama_parse_api_key.get_secret_value():
        issues.append("missing MFA_LLAMA_PARSE_API_KEY")
    if issues:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "issues": issues},
        )
    return ReadinessResponse(status="ready")


@router.post("/schema", tags=["pipeline"])
async def post_schema(file: UploadFile = File(...)) -> dict[str, Any]:
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    started = time.perf_counter()
    try:
        schema = extract_schema(io.BytesIO(contents))
    except Exception as exc:
        log.exception("schema.parse_failed", filename=file.filename)
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {exc}") from exc

    if not schema:
        raise HTTPException(status_code=400, detail="PDF has no AcroForm fields")

    log.info(
        "schema.extracted",
        filename=file.filename,
        field_count=len(schema),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return schema


@router.post("/extract", response_model=ExtractResponse, tags=["pipeline"])
def post_extract(
    body: ExtractRequest,
    settings: SettingsDep,
    strict: bool = Query(False, description="Fail with 422 if validation finds any errors"),
) -> ExtractResponse:
    if body.lab_result_text is None and body.lab_result_pdf_b64 is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either lab_result_text or lab_result_pdf_b64",
        )

    if body.lab_result_pdf_b64 is not None:
        try:
            pdf_bytes = base64.b64decode(body.lab_result_pdf_b64)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid base64 in lab_result_pdf_b64: {exc}") from exc
        lab_text = parse_lab_pdf(io.BytesIO(pdf_bytes), settings=settings)
    else:
        lab_text = preprocess_lab_text(body.lab_result_text or "")

    try:
        answers = run_extraction(
            schema=body.schema_,
            lab_result_text=lab_text,
            soap_notes=body.soap_notes,
            demographics=body.demographics,
            settings=settings,
        )
    except Exception as exc:
        log.exception("extract.upstream_failed")
        raise HTTPException(status_code=502, detail=f"LLM upstream failure: {exc}") from exc

    errors = run_validations(answers)
    validation: dict[str, Any] = {"ok": not errors, "errors": errors}

    if strict and errors:
        raise HTTPException(status_code=422, detail={"validation": validation})

    return ExtractResponse(answers=answers, validation=validation)


@router.post(
    "/populate",
    tags=["pipeline"],
    responses={200: {"content": {"application/pdf": {}}}},
)
def post_populate(body: PopulateRequest) -> Response:
    try:
        pdf_bytes = base64.b64decode(body.fillable_pdf_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 in fillable_pdf_b64: {exc}") from exc

    schema_keys = set(body.schema_.keys())
    answer_keys = set(body.answers.keys())
    unknown = answer_keys - schema_keys
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Answers contain keys not present in schema: {sorted(unknown)[:5]}",
        )

    try:
        populated = populate_pdf(io.BytesIO(pdf_bytes), body.schema_, body.answers)
    except Exception as exc:
        log.exception("populate.failed")
        raise HTTPException(status_code=400, detail=f"Failed to populate PDF: {exc}") from exc

    return Response(content=populated, media_type="application/pdf")
