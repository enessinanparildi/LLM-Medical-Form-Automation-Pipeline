import json
import re
from collections import defaultdict

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re

from utils import get_llamaindex_gemini
from llama_index.core import PromptTemplate

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")

class SoapExtraction(BaseModel):
    patient_age: Optional[int] = Field(
        description="Patient age in years if explicitly stated"
    )
    chief_complaint: Optional[str] = Field(
        description="Primary complaint stated by the patient"
    )
    diagnosis: Optional[str] = Field(
        description="Assessment or diagnosis if explicitly stated"
    )
    medications: List[str] = Field(
        description="Medications explicitly mentioned in the plan"
    )
    visit_date: Optional[str] = Field(
        description="Visit date in ISO format YYYY-MM-DD"
    )

    @field_validator("visit_date")
    @classmethod
    def validate_date(cls, v):
        if v is None:
            return v
        if not DATE_REGEX.match(v):
            raise ValueError("visit_date must be YYYY-MM-DD")
        return v




def extract_structured() -> SoapExtraction:
    template = (
        """
    You are a clinical information extraction system.

    Extract ONLY information explicitly stated in the SOAP note.
    If a field is not present, return null.
    Do NOT infer or guess.

    SOAP NOTE:
    {soap_note}
    """
    )

    train_data = load_json("./data/soap_training_data.json")
    final_str = ""
    for d in train_data:
        final_str = d["input_text"]  + "\n" + "-----------------" + "\n" +  final_str

    text_list = [d["input_text"] for d in train_data]
    llm = get_llamaindex_gemini()

    # Create structured LLM with Pydantic model
    structured_llm = llm.as_structured_llm(output_cls=SoapExtraction)
    prompt_template = PromptTemplate(template)

    # Format the prompt
    responses = []
    for text in text_list:
        formatted_prompt = prompt_template.format(soap_note=text)
        # Get structured response
        response = structured_llm.complete(formatted_prompt)
        responses.append(response.raw)
            # The response.raw is the Pydantic model instance
    extraction_result = responses

    return extraction_result

FIELDS = [
    "patient_age",
    "chief_complaint",
    "diagnosis",
    "medications",
    "visit_date",
]

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def is_correct(pred, truth):
    if truth is None:
        return pred is None
    return pred == truth

def check_format(field, value):
    if value is None:
        return True
    if field == "patient_age":
        return isinstance(value, int)
    if field == "medications":
        return isinstance(value, list)
    if field == "visit_date":
        return isinstance(value, str) and DATE_REGEX.match(value)
    return isinstance(value, str)

def evaluate(dataset, outputs):

    field_correct = defaultdict(int)
    field_total = defaultdict(int)
    formatting_errors = 0
    total_fields = 0

    hallucinations = 0
    hallucination_opportunities = 0

    for ord, example in enumerate(dataset):
        truth = example["ground_truth"]
        pred = outputs[ord]

        for field in FIELDS:
            gt_value = truth[field]
            pred_value = getattr(pred, field)

            field_total[field] += 1
            total_fields += 1

            # Accuracy
            if is_correct(pred_value, gt_value):
                field_correct[field] += 1

            # Formatting
            if not check_format(field, pred_value):
                formatting_errors += 1

            # Hallucination check
            if gt_value is None:
                hallucination_opportunities += 1
                if pred_value not in (None, [], ""):
                    hallucinations += 1

    results = {
        "field_accuracy": {
            field: round(field_correct[field] / field_total[field], 3)
            for field in FIELDS
        },
        "formatting_error_rate": round(formatting_errors / total_fields, 3),
        "hallucination_rate": round(
            hallucinations / hallucination_opportunities, 3
        ) if hallucination_opportunities else 0.0
    }

    return results

def main():
    result = extract_structured()
    dataset = load_json("./data/soap_training_data.json")
    outputs = result

    results = evaluate(dataset, outputs)

    print("\n=== Evaluation Results ===")
    print("\nField-Level Accuracy:")
    for field, acc in results["field_accuracy"].items():
        print(f"  {field}: {acc}")

    print(f"\nFormatting Error Rate: {results['formatting_error_rate']}")
    print(f"Hallucination Rate: {results['hallucination_rate']}")

if __name__ == "__main__":
    main()
