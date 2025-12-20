import json
import re
from collections import defaultdict

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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
    outputs_by_id = {o["id"]: o["output"] for o in outputs}

    field_correct = defaultdict(int)
    field_total = defaultdict(int)
    formatting_errors = 0
    total_fields = 0

    hallucinations = 0
    hallucination_opportunities = 0

    for example in dataset:
        ex_id = example["id"]
        truth = example["ground_truth"]
        pred = outputs_by_id.get(ex_id, {})

        for field in FIELDS:
            gt_value = truth[field]
            pred_value = pred.get(field)

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
    dataset = load_json("eval_dataset.json")
    outputs = load_json("model_outputs.json")

    results = evaluate(dataset, outputs)

    print("\n=== Evaluation Results ===")
    print("\nField-Level Accuracy:")
    for field, acc in results["field_accuracy"].items():
        print(f"  {field}: {acc}")

    print(f"\nFormatting Error Rate: {results['formatting_error_rate']}")
    print(f"Hallucination Rate: {results['hallucination_rate']}")

if __name__ == "__main__":
    main()
