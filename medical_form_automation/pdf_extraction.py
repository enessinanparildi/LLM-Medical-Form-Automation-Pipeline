"""Parse a fillable PDF form into a JSON schema describing its fields."""

import json
from pathlib import Path
from typing import Any, BinaryIO

from pypdf import PdfReader


RADIO_FLAG = 1 << 15
PUSHBUTTON_FLAG = 1 << 16


def _get_bbox(reader: PdfReader) -> dict[str, Any]:
    bbox_by_field: dict[str, Any] = {}
    for page in reader.pages:
        annots = page.get("/Annots")
        if annots is None:
            continue
        for annot_ref in annots:
            annot = annot_ref.get_object()
            if annot.get("/FT") == "/Tx":
                key = annot.get("/T")
                if key is not None:
                    bbox_by_field[str(key).strip().lower()] = annot.get("/Rect")
    return bbox_by_field


def extract_schema(pdf_source: str | Path | BinaryIO) -> dict[str, Any]:
    """Read a fillable PDF and return its form schema keyed by lowercased /T field name."""
    reader = PdfReader(pdf_source)
    bbox_by_field = _get_bbox(reader)

    fields = reader.get_fields() or {}
    schema: dict[str, Any] = {}

    for name, field in fields.items():
        field_type = field.get("/FT")
        actual_name = field.get("/TU")
        t_name = field.get("/T")
        if t_name is None:
            continue
        norm_key = str(t_name).strip().lower()

        if field_type == "/Tx":
            schema[norm_key] = {
                "label": actual_name,
                "normalized_name": norm_key,
                "bbox": bbox_by_field.get(norm_key),
                "type": "text",
                "pdf_field_name": name,
            }
        elif field_type == "/Btn":
            flags = field.get("/Ff", 0) or 0
            if flags & RADIO_FLAG or flags & PUSHBUTTON_FLAG:
                continue

            checkbox_opts: list[str] = []
            bbox: list[Any] = []
            if "/Kids" in field:
                for kid_ref in field["/Kids"]:
                    kid = kid_ref.get_object()
                    ap = kid.get("/AP", {})
                    n = ap.get("/N", {}) if ap else {}
                    keys = list(n.keys()) if hasattr(n, "keys") else []
                    if keys:
                        opt_key = keys[0]
                        checkbox_opts.append(str(opt_key)[1:])
                    if "/Rect" in kid:
                        bbox.append(kid["/Rect"])
            elif "/Rect" in field:
                bbox.append(field["/Rect"])

            schema[norm_key] = {
                "label": actual_name,
                "normalized_name": norm_key,
                "bbox": bbox,
                "type": "checkbox",
                "checkbox_opts": checkbox_opts,
                "pdf_field_name": name,
            }

    return schema


def main() -> None:
    pdf_path = Path("./data/form_fillable.pdf")
    out_path = Path("./output/schema.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema = extract_schema(pdf_path)
    out_path.write_text(json.dumps(schema, indent=4, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
