from llama_index.llms.google_genai import GoogleGenAI
import json


def compare_with_ground_truth(llm_data_dict):
    def normalize_value(value):
        """Normalize value for comparison (handles None, case, whitespace)"""
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip().lower()
        return str(value).strip().lower()

    ground_truth = {
        "first name": "Peter Julius Fern",
        "areacode": "613",
        "phonea": "656",
        "phoneb": "5890",
        "areacode1": "647",
        "phonea1": "666",
        "phoneb1": "8888",
        "address": "45 Maple Ave, Toronto, ON, K7L 3V8",
        "employer name": None,
        "contract": "9696178816",  # CORRECTED
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
        "doctor": "Consulting Specialist",  # CORRECTED
        "doctor_other": None,
        "diagnosis_primary1": "stable angina",
        "diagnosis_primary2": "Hypertension",
        "diagnosis_secondary1": "GERD",
        "diagnosis_secondary2": "Hyperlipidemia",
        "date_childbirth_d": None,
        "date_childbirth_m": None,
        "date_childbirth_y": None,
        "delivery": None
    }
    correct = 0
    incorrect = 0
    total = len(ground_truth)

    correct_fields = []
    incorrect_fields = []
    missing_fields = []

    for key, expected_value in ground_truth.items():
        # Check if key exists in LLM output
        if key not in llm_data_dict:
            missing_fields.append(key)
            incorrect += 1
            continue

        # Extract value from LLM dict (nested structure)
        llm_value = llm_data_dict[key].get("value") if isinstance(llm_data_dict[key], dict) else llm_data_dict[key]

        # Normalize values for comparison
        normalized_expected = normalize_value(expected_value)
        normalized_llm = normalize_value(llm_value)

        # Compare values
        if normalized_expected == normalized_llm:
            correct += 1
            correct_fields.append(key)
        else:
            incorrect += 1
            incorrect_fields.append({
                "field": key,
                "expected": expected_value,
                "got": llm_value
            })

    # Calculate accuracy
    accuracy = (correct / total) * 100 if total > 0 else 0

    # Build results
    results = {
        "accuracy": round(accuracy, 2),
        "correct_count": correct,
        "incorrect_count": incorrect,
        "total_fields": total,
        "correct_fields": correct_fields,
        "incorrect_fields": incorrect_fields,
        "missing_fields": missing_fields
    }
    print(results)

    return results


def get_field_data():

    with open('./output/schema.json', 'r') as file:
        field_data = json.load(file)

    def generate_combined_string(fields_dict):
        lines = []

        for field_name, field_data in fields_dict.items():
            if field_data['type'] == 'checkbox':
                options = ', '.join(field_data['checkbox_opts'])
                lines.append(f"• {field_name} , {field_data['label']} (Options: {options})")
            else:
                lines.append(f"• {field_name} : {field_data['label']}")

        return '\n'.join(lines), lines

    # Usage
    combined_str, line_list = generate_combined_string(field_data)
    return combined_str, line_list, field_data


def get_llamaindex_gemini() -> GoogleGenAI:
    SAFE = [
        {
            "category": "HARM_CATEGORY_DANGEROUS",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_NONE",
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_NONE",
        },
    ]
    max_tokens = 100000
    context_window = 10000
    llm_gemini = GoogleGenAI(model_name="models/gemini-3.0-flash", api_key=gemini_api_key_2,
                        temperature=0.1, safety_settings=SAFE, response_logprobs=True)
    return llm_gemini



def get_source_priority_list_per_field():
    """
        Return per-field source reliability ordering (highest -> lowest).

        Sources:
          S1 = Lab result / insurance form text (PDF OCR; good for policy/work-status fields)
          S2 = SOAP notes (clinician notes; best for diagnoses/medications/vitals)
          S3 = Patient demographics JSON (best for identity/contact/DOB/handedness)

        How to use:
          - When two sources disagree for the same field, prefer the first source in the list.
          - If the top source is missing/blank for that field, fall back to the next.

        Rationale (high level):
          - Identity/contact info is most reliably stored in structured demographics (S3).
          - Clinical content (diagnoses, meds, vitals) is most reliable in SOAP notes (S2).
          - Administrative/insurance/work/disability fields are often most reliable on the form (S1).

        We can use this as an alternative information prior to guide the LLM. The below list is just an example.
    """



    FIELD_SOURCE_PRIORITY = {
        # Identity / contact: demographics is usually most reliable
        "first name": ["S3", "S2", "S1"],
        "areacode": ["S3", "S2", "S1"],
        "phonea": ["S3", "S2", "S1"],
        "phoneb": ["S3", "S2", "S1"],
        "areacode1": ["S3", "S2", "S1"],
        "phonea1": ["S3", "S2", "S1"],
        "phoneb1": ["S3", "S2", "S1"],
        "address": ["S3", "S2", "S1"],

        # Employer/insurance identifiers: often on forms; sometimes in demographics; rarely in SOAP
        "employer name": ["S1", "S3", "S2"],
        "company_name": ["S1", "S3", "S2"],
        "contract": ["S1", "S3", "S2"],
        "cert": ["S1", "S3", "S2"],

        # DOB: demographics > SOAP > lab form
        "date_of_birth_d": ["S3", "S2", "S1"],
        "date_of_birth_m": ["S3", "S2", "S1"],
        "date_of_birth_y": ["S3", "S2", "S1"],

        # Work status dates: typically in form (disability/insurance) > SOAP > demographics
        "date_last_d": ["S1", "S2", "S3"],
        "date_last_m": ["S1", "S2", "S3"],
        "date_last_y": ["S1", "S2", "S3"],
        "date_return_d": ["S1", "S2", "S3"],
        "date_return_m": ["S1", "S2", "S3"],
        "date_return_y": ["S1", "S2", "S3"],

        # Medications: SOAP is best; demographics sometimes; lab form rarely
        "medication1": ["S2", "S3", "S1"],
        "medication2": ["S2", "S3", "S1"],
        "medication3": ["S2", "S3", "S1"],
        "medication4": ["S2", "S3", "S1"],
        "medication5": ["S2", "S3", "S1"],
        "dose1": ["S2", "S3", "S1"],
        "dose2": ["S2", "S3", "S1"],
        "dose3": ["S2", "S3", "S1"],
        "dose4": ["S2", "S3", "S1"],
        "dose5": ["S2", "S3", "S1"],
        "often1": ["S2", "S3", "S1"],
        "often2": ["S2", "S3", "S1"],
        "often3": ["S2", "S3", "S1"],
        "often4": ["S2", "S3", "S1"],
        "often5": ["S2", "S3", "S1"],

        # Vitals / anthropometrics: usually SOAP; sometimes form; rarely demographics
        "height": ["S2", "S1", "S3"],
        "weight": ["S2", "S1", "S3"],

        # Hand dominance: usually intake/demographics > SOAP > lab
        "hand": ["S3", "S2", "S1"],

        # Doctor / provider role: typically form > SOAP; not usually demographics JSON
        "doctor": ["S1", "S2", "S3"],
        "doctor_other": ["S1", "S2", "S3"],

        # Diagnoses: SOAP is most reliable; sometimes form; rarely demographics
        "diagnosis_primary1": ["S2", "S1", "S3"],
        "diagnosis_primary2": ["S2", "S1", "S3"],
        "diagnosis_secondary1": ["S2", "S1", "S3"],
        "diagnosis_secondary2": ["S2", "S1", "S3"],

        # Pregnancy/childbirth fields: typically form > SOAP > demographics
        "date_childbirth_d": ["S1", "S2", "S3"],
        "date_childbirth_m": ["S1", "S2", "S3"],
        "date_childbirth_y": ["S1", "S2", "S3"],
        "delivery": ["S1", "S2", "S3"],
    }
    return FIELD_SOURCE_PRIORITY
