"""SOAP-only evaluation against data/soap_training_data.json."""

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from llama_index.core import PromptTemplate
from pydantic import BaseModel, Field, field_validator

from medical_form_automation.utils import get_llamaindex_gemini


DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")

FIELDS = [
    "patient_age",
    "chief_complaint",
    "diagnosis",
    "medications",
    "visit_date",
]


class SoapExtraction(BaseModel):
    patient_age: Optional[int] = Field(description="Patient age in years if explicitly stated")
    chief_complaint: Optional[str] = Field(description="Primary complaint stated by the patient")
    diagnosis: Optional[str] = Field(description="Assessment or diagnosis if explicitly stated")
    medications: list[str] = Field(description="Medications explicitly mentioned in the plan")
    visit_date: Optional[str] = Field(description="Visit date in ISO format YYYY-MM-DD")

    @field_validator("visit_date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not DATE_REGEX.match(v):
            raise ValueError("visit_date must be YYYY-MM-DD")
        return v


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def extract_structured(jsonl_path: str | Path = "./data/soap_training_data.json") -> list[SoapExtraction]:
    template = PromptTemplate(
        """
You are a clinical information extraction system.

Extract ONLY information explicitly stated in the SOAP note.
If a field is not present, return null.
Do NOT infer or guess.

SOAP NOTE:
{soap_note}
"""
    )
    train_data = load_jsonl(jsonl_path)
    text_list = [d["input_text"] for d in train_data]

    llm = get_llamaindex_gemini()
    structured_llm = llm.as_structured_llm(output_cls=SoapExtraction)

    responses: list[SoapExtraction] = []
    for text in text_list:
        formatted = template.format(soap_note=text)
        response = structured_llm.complete(formatted)
        responses.append(response.raw)
    return responses


def is_correct(pred: Any, truth: Any) -> bool:
    if truth is None:
        return pred is None
    return pred == truth


def check_format(field: str, value: Any) -> bool:
    if value is None:
        return True
    if field == "patient_age":
        return isinstance(value, int)
    if field == "medications":
        return isinstance(value, list)
    if field == "visit_date":
        return isinstance(value, str) and bool(DATE_REGEX.match(value))
    return isinstance(value, str)


def evaluate(dataset: list[dict[str, Any]], outputs: list[SoapExtraction]) -> dict[str, Any]:
    field_correct: dict[str, int] = defaultdict(int)
    field_total: dict[str, int] = defaultdict(int)
    formatting_errors = 0
    total_fields = 0
    hallucinations = 0
    hallucination_opportunities = 0

    for ord_, example in enumerate(dataset):
        truth = example["ground_truth"]
        pred = outputs[ord_]

        for field in FIELDS:
            gt_value = truth[field]
            pred_value = getattr(pred, field)
            field_total[field] += 1
            total_fields += 1

            if is_correct(pred_value, gt_value):
                field_correct[field] += 1
            if not check_format(field, pred_value):
                formatting_errors += 1
            if gt_value is None:
                hallucination_opportunities += 1
                if pred_value not in (None, [], ""):
                    hallucinations += 1

    return {
        "field_accuracy": {
            field: round(field_correct[field] / field_total[field], 3) for field in FIELDS
        },
        "formatting_error_rate": round(formatting_errors / total_fields, 3),
        "hallucination_rate": (
            round(hallucinations / hallucination_opportunities, 3)
            if hallucination_opportunities
            else 0.0
        ),
    }


def main() -> None:
    dataset = load_jsonl("./data/soap_training_data.json")
    outputs = extract_structured("./data/soap_training_data.json")
    results = evaluate(dataset, outputs)

    print("\n=== Evaluation Results ===")
    print("\nField-Level Accuracy:")
    for field, acc in results["field_accuracy"].items():
        print(f"  {field}: {acc}")
    print(f"\nFormatting Error Rate: {results['formatting_error_rate']}")
    print(f"Hallucination Rate: {results['hallucination_rate']}")


if __name__ == "__main__":
    main()
