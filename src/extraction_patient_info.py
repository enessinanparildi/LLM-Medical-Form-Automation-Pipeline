from llama_parse import LlamaParse
from llama_index.core import PromptTemplate
from utils import get_field_data, compare_with_ground_truth, get_llamaindex_gemini
from data_validation import parse_address, validate_dob, validate_area_code
import json
from pydantic_defs import prompt_llm_structured
import re

llama_parse_api_key = ""

#TODO: Add structured extraction: Structured extraction added but we encountered an error:
# The specified schema produces a constraint that has too many states for serving.  Typical causes of this error are schemas with lots of text (for example, very long property or enum names), schemas with long array length limits (especially when nested), or schemas using complex value matchers (for example, integers or numbers with minimum/maximum bounds or strings with complex formats like date-time)'

#TODO: RAG retrieval from documents; For this application since the documents are small, RAG is not needed
# But RAG retrieval could still be useful

#


def prompt_llm(patient_demographic_data, soap_content, lab_result_text, field_data):
    template = (
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

    qa_template = PromptTemplate(template)
    messages = qa_template.format(lab_result_text=lab_result_text, soap_text=soap_content, field_list_str = field_data,
                                  json_data = patient_demographic_data)

    llm_gemini = get_llamaindex_gemini()

    out = llm_gemini.complete(messages)
    print(out)
    output_text = out.text
    return output_text, out



def get_lab_result_text():
    pdf_url = "./data/lab_result.pdf"

    parser = LlamaParse(
        api_key=llama_parse_api_key,  # can also be set in your env as LLAMA_CLOUD_API_KEY
        result_type="markdown",  # "markdown" and "text" are available
        num_workers=4,  # if multiple files passed, split in `num_workers` API calls
        verbose=True,
        language="en",
    )
    parsed_documents = parser.load_data(pdf_url)

    merged_str = ''
    for documents in parsed_documents:
        merged_str = merged_str + "\n" + documents.text
    merged_str = merged_str.replace("Dr", "Doctor")
    merged_str = merged_str.replace("MD", "Medical Doctor")
    merged_str = merged_str.replace("dr", "Doctor")
    merged_str = merged_str.replace("-", " ")

    return merged_str

def get_other_data():
    # Open the file and load the content
    with open('./data/demographics.json', 'r') as file:
        patient_demographic_data = json.load(file)

    with open('./data/soap_notes.txt', 'r', encoding='utf-8') as file:
        soap_content = file.read()

    return patient_demographic_data, soap_content


def data_validation_check(llm_data_dict):
    field_to_validate = ["areacode", "phonea", "phoneb", "areacode1", "phonea1", "phoneb1", "address"]
    date_fields = [("date_of_birth_d", "date_of_birth_m", "date_of_birth_y"), ("date_last_d", "date_last_m", "date_last_y"),
                   ("date_return_d", "date_return_m", "date_return_y" ),
                   ("date_childbirth_d", "date_childbirth_m", "date_childbirth_y")]

    for field in field_to_validate:
        if field == "areacode":
            value = llm_data_dict[field]['value']
            result = validate_area_code("1", value)
            if result == "Invalid area code" or result == "Error" or result == "Invalid Format":
                raise ValueError(f"Invalid area code format: {value}")
        elif field == "phonea" or field == "phonea1":
            value = llm_data_dict[field]['value']
            if len(value) == 3 and value.isdecimal():
                pass
            else:
                raise ValueError(f"Invalid phone number format: {value}")
        elif field == "phoneb" or field == "phoneb1":
            value = llm_data_dict[field]['value']
            if len(value) == 4 and value.isdecimal():
                pass
            else:
                raise ValueError(f"Invalid phone number format: {value}")
        # Address parser here did not work, more advanced address parser is needed. I skipped this part.
        #elif field == "address":
        #   value = llm_data_dict[field]['value']
        #   res = parse_address(value)
        #   if not res["outcome"]:
        #      raise ValueError(f"Invalid address format: {value}")
        else:
            pass

    for date_set in date_fields:
        date_1 = llm_data_dict[date_set[0]]['value']
        date_2 = llm_data_dict[date_set[1]]['value']
        date_3 = llm_data_dict[date_set[2]]['value']
        if date_1 != "null" and date_2 != "null" and date_3 != "null":
            validate_dob(date_set[0], date_set[1], date_set[2])
        else:
            pass

def extract_json_object(text):
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("No JSON object found")
    return json.loads(m.group(0))

if __name__ == "__main__":
    structured_extraction = False
    patient_demographic_data, soap_content = get_other_data()
    lab_result_text = get_lab_result_text()
    field_data_str, line_list, field_data_json = get_field_data()
    print(field_data_str)

    # Extracts and validates data using LLM; persists results
    if not structured_extraction:
        output_text, out = prompt_llm(patient_demographic_data, soap_content, lab_result_text, field_data_str)
        print(output_text)

        json_text = extract_json_object(output_text)

        with open("./output/answers.json", "w", encoding="utf-8") as f:
            json.dump(json_text, f, indent=4, ensure_ascii=False)

        out_json = json.loads(json_text)
        data_validation_check(out_json)
        compare_with_ground_truth(out_json)
        assert len(out_json.keys()) == len(field_data_json.keys())

    else:
        output_text = prompt_llm_structured(patient_demographic_data, soap_content, lab_result_text, field_data_str, field_data_json)
        print(output_text)
        data_validation_check(output_text)
        compare_with_ground_truth(output_text)
        assert len(output_text.keys()) == len(field_data_json.keys())
        with open("./output/answers.json", "w", encoding="utf-8") as f:
            json.dump(output_text, f, indent=4, ensure_ascii=False)



