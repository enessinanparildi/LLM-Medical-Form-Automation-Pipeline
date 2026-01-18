from pypdf import PdfReader, PdfWriter
import json

reader = PdfReader("./data/form_fillable.pdf")
writer = PdfWriter()

def create_llm_answer_field_dict():
    with open('./output/out_extracted.json', 'r') as file:
        llm_out_answer_dict = json.load(file)

    llm_out_answer_dict = json.loads(llm_out_answer_dict)
    with open('./output/schema.json', 'r') as file:
        field_data_dict = json.load(file)

    answer_dict = dict()
    
    for key in field_data_dict.keys():
        val = llm_out_answer_dict[key]["value"]
        sec_key = field_data_dict[key]["pdf_field_name"]

        if field_data_dict[key]['type'] == 'text':
            answer_dict[sec_key] = val
        elif field_data_dict[key]['type'] == 'checkbox':
            if val is not None:
                answer_dict[sec_key] = "/" + val
        else:
            raise ValueError("Invalid field type")

    return answer_dict


def main_populate():
    answer_dict = create_llm_answer_field_dict()

    fields = reader.get_fields()

    writer.append(reader)

    writer.update_page_form_field_values(
        writer.pages[0],
        fields= answer_dict,
        auto_regenerate=False,
    )

    writer.write("./output/pdf_populated.pdf")

if __name__ == "__main__":
    main_populate()
