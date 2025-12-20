from pypdf import PdfReader
import json

def get_bbox(reader):
    data_dict_bbox = {}
    for page in reader.pages:
        for annot_ref in page["/Annots"]:
            annot = annot_ref.get_object()
            if annot.get('/FT') == '/Tx':
                data_dict_bbox[annot.get("/T").strip().lower()] = annot.get('/Rect')
    return data_dict_bbox

def process_pdf(reader):

    data_dict_bbox = get_bbox(reader)

    RADIO_FLAG = 1 << 15
    PUSHBUTTON_FLAG = 1 << 16

    fields = reader.get_fields()
    fields_processed = []
    field_raw_data = []
    field_json_data = dict()

    for name, field in fields.items():
        name_ = name.strip().lower()

        field_type = field.get('/FT')
        value = field.get('/V')
        actual_name = field.get('/TU')

        data_dict = {}
        if field_type == '/Tx':
            print(f"TEXT FIELD [{actual_name}]: {value}")

            fields_processed.append(f"TEXT FIELD [{actual_name,  name_}]: {value}")

            data_dict["name"] = actual_name + " , " + field.get("/T").strip().lower()
            data_dict["field_type"] = "text"
            data_dict["bbox"] = data_dict_bbox.get(field.get("/T").strip().lower())

            field_json_data[field.get("/T").strip().lower()] = {"label": actual_name,
                                                                "normalized_name": field.get("/T").strip().lower(),
                                                                "bbox": data_dict["bbox"],
                                                                "type": "text",
                                                                "pdf_field_name": name}

        elif field_type == '/Btn':
            flags = field.get('/Ff', 0)

            is_radio = flags & RADIO_FLAG
            is_pushbutton = flags & PUSHBUTTON_FLAG

            if not is_radio and not is_pushbutton:
                data_dict["field_type"] = "checkbox"
                is_ticked = value != "/Off" and value is not None
                status = "Ticked" if is_ticked else "Empty"

                print(f"TICK BOX   [{actual_name}]: {status} (Raw value: {value})")

                fields_processed.append(f"TICK BOX   [{actual_name,  name}]: {status} (Raw value: {value})")

                data_dict["name"] = actual_name + " , " + field.get("/T").strip().lower()
                data_dict["checkbox_opts"] = []
                data_dict["bbox"] = []

                if "/Kids" in field:
                    for kid_ref in field["/Kids"]:
                        kid = kid_ref.get_object()
                        data_dict["checkbox_opts"].append(list(kid['/AP']['/N'].keys())[0][1:])
                        if "/Rect" in kid:
                            print(f"Field: {name} | BBox (Rect): {kid['/Rect']}")
                            data_dict["bbox"].append(kid['/Rect'])
                else:
                    if "/Rect" in field:
                        print(f"Field: {name} | BBox (Rect): {field['/Rect']}")
                        data_dict["bbox"].append(field['/Rect'])


                field_json_data[field.get("/T").strip().lower()] = {"label": actual_name,
                                                                    "normalized_name": field.get("/T").strip().lower(),
                                                                    "bbox": data_dict["bbox"],
                                                                    "type": "checkbox",
                                                                    "checkbox_opts" : data_dict["checkbox_opts"],
                                                                    "pdf_field_name": name}
        else:
            pass

        if len(data_dict) > 0:
            field_raw_data.append(data_dict)

    return field_json_data

def main():
    reader = PdfReader("./data/form_fillable.pdf")
    field_json_data = process_pdf(reader)

    with open("./output/schema.json", "w", encoding="utf-8") as f:
        json.dump(field_json_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()
