from pydantic import BaseModel, Field, create_model, field_validator
from typing import Optional, List, Union, Dict, Any, Type
import json
from utils import get_llamaindex_gemini


class Citation(BaseModel):
    """Represents a citation from a source document."""
    source: str = Field(
        description="Source identifier: S1 (Lab result), S2 (SOAP notes), or S3 (Patient JSON)"
    )
    quote: str = Field(
        description="Supporting quote or snippet from the source"
    )


class FieldExtraction(BaseModel):
    """Represents the extraction result for a single field."""
    value: Optional[Union[str, int, float, List[str]]] = Field(
        description="Extracted value (string/number/list) or null if not found"
    )
    source: str = Field(
        description="Source identifier: S1 (Lab result), S2 (SOAP notes), or S3 (Patient JSON) or null if not found"
    )
    reasoning: str = Field(
        description="Brief explanation of how the value was chosen, including conflict resolution or null if not found"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0, 0.0 if not found"
    )

    #@field_validator('confidence')
    #@classmethod
    #def validate_confidence(cls, v):
    #    if not 0.0 <= v <= 1.0:
    #        raise ValueError('Confidence must be between 0.0 and 1.0')
    #    return round(v, 2)


def create_pydantic_model(field_dict):
    dict_final = {}
    for key, value in field_dict.items():
        dict_final[key] = (FieldExtraction, Field(description=f"Extraction for {key}"))
    return create_model('OutputExtraction', **dict_final)


def get_structured_extraction_prompt_template() -> str:
    """Return the prompt template for extraction."""
    return """You are an information extraction system.
Use ONLY the information in the provided sources. Do NOT guess, infer, or fabricate.

You have a general understanding of how medical bureaucracy and insurance policy works in Canada and the United States.
For example, in Canada policy number is represented as a healthcard number.

FIELDS TO FILL:
{field_list_str}

SOURCES (cite these explicitly):
[S1] Lab result form (unstructured text):
{lab_result_text}

[S2] SOAP notes (unstructured text):
{soap_text}

[S3] Patient personal data (JSON):
{json_data}

EXTRACTION RULES:
0) Field spec echo (required):
   - For each output key, set field_spec to the EXACT matching line from FIELDS TO FILL that begins with that key.
   - Copy it verbatim (including checkbox options if present).
   - If you cannot find a matching line, set field_spec = null.
1) Coverage: Fill as many fields as possible. If not explicitly stated, set value = null.
2) Conflicts: If sources disagree, prefer S3 > S2 > S1. If still ambiguous, set null.
3) Formatting:
   - Dates: YYYY-MM-DD when available; otherwise keep partial (YYYY-MM or YYYY) as a string.
   - Phone: digits only. If a full phone appears, split into areacode (3), first part (3), second part (4) when possible.
   - Height/weight: keep numeric + unit if present; otherwise numeric only.
4) Checkbox fields:
   - Return the selected option exactly as listed in the field options.
   - If multiple selections are explicitly indicated, return a list of strings.
   - If selection is not explicit, return null.
5) Evidence requirement:
   - Every non-null value MUST include at least one citation with a short supporting quote/snippet.

Confidence guidance (explain briefly in reasoning):
- 0.90-1.00: explicit exact match in a single source; increase if corroborated across sources
- 0.60-0.89: explicit but requires mild normalization or clearly implied by nearby context
- 0.30-0.59: weak/partial evidence, competing candidates, or incomplete value
- 0.00: value is null

Extract all fields according to the schema provided."""


def prompt_llm_structured(
        patient_demographic_data: Dict,
        soap_content: str,
        lab_result_text: str,
        field_data_str: str,
        field_names_json: List[str]
):
    """
    Extract information using structured output with Pydantic model.
    """
    llm = get_llamaindex_gemini()
    MedicalFormExtraction = create_pydantic_model(field_names_json)

    # Create structured LLM with Pydantic model
    structured_llm = llm.as_structured_llm(output_cls=MedicalFormExtraction)

    # Format the prompt
    prompt_template = get_structured_extraction_prompt_template()
    formatted_prompt = prompt_template.format(
        field_list_str=field_data_str,
        lab_result_text=lab_result_text,
        soap_text=soap_content,
        json_data=json.dumps(patient_demographic_data, indent=2)
    )

    # Get structured response
    response = structured_llm.complete(formatted_prompt)

    # The response.raw is the Pydantic model instance
    extraction_result = response.raw

    return extraction_result
