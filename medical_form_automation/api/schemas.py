"""Request and response models for the FastAPI surface."""

from typing import Annotated, Any, Optional

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    schema_: Annotated[dict[str, Any], Field(alias="schema", description="Output of POST /schema")]
    soap_notes: Annotated[str, Field(description="Raw SOAP notes text")]
    demographics: Annotated[dict[str, Any], Field(description="Patient demographics JSON")]
    lab_result_text: Optional[str] = Field(
        default=None, description="Pre-parsed lab result markdown text"
    )
    lab_result_pdf_b64: Optional[str] = Field(
        default=None,
        description="Base64-encoded lab result PDF; server runs LlamaParse if provided",
    )

    model_config = {"populate_by_name": True}


class ValidationError(BaseModel):
    field: str
    value: Any
    error: Optional[str]


class ExtractResponse(BaseModel):
    answers: dict[str, Any]
    validation: dict[str, Any]


class PopulateRequest(BaseModel):
    schema_: Annotated[dict[str, Any], Field(alias="schema")]
    answers: dict[str, Any]
    fillable_pdf_b64: Annotated[str, Field(description="Base64-encoded fillable PDF to populate")]

    model_config = {"populate_by_name": True}


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadinessResponse(BaseModel):
    status: str
    issues: list[str] = []


class ErrorResponse(BaseModel):
    detail: str
    request_id: str
