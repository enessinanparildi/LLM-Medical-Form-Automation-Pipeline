"""Populate a fillable PDF form using extracted answers + the original schema."""

import io
import json
from pathlib import Path
from typing import Any, BinaryIO

from pypdf import PdfReader, PdfWriter


def build_pdf_field_values(schema: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    """Map answer keys → real PDF field names, prefixing checkbox values with '/'.

    Skips fields whose answer is null or missing rather than writing an empty string.
    """
    out: dict[str, Any] = {}
    for key, field_spec in schema.items():
        entry = answers.get(key)
        if entry is None:
            continue
        value = entry.get("value") if isinstance(entry, dict) else entry

        pdf_name = field_spec["pdf_field_name"]
        ftype = field_spec["type"]

        if ftype == "text":
            if value is None:
                continue
            out[pdf_name] = value
        elif ftype == "checkbox":
            if value is None:
                continue
            if isinstance(value, list):
                if not value:
                    continue
                value = value[0]
            out[pdf_name] = "/" + str(value)
        else:
            raise ValueError(f"Unknown field type for {key}: {ftype}")

    return out


def populate_pdf(
    fillable_pdf: str | Path | BinaryIO,
    schema: dict[str, Any],
    answers: dict[str, Any],
) -> bytes:
    """Fill the PDF in memory and return the populated PDF bytes."""
    reader = PdfReader(fillable_pdf)
    writer = PdfWriter()
    writer.append(reader)

    field_values = build_pdf_field_values(schema, answers)
    writer.update_page_form_field_values(
        writer.pages[0],
        fields=field_values,
        auto_regenerate=False,
    )

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def main() -> None:
    """CLI entry point: reads schema.json + answers.json, writes pdf_populated.pdf."""
    schema = json.loads(Path("./output/schema.json").read_text(encoding="utf-8"))
    answers = json.loads(Path("./output/answers.json").read_text(encoding="utf-8"))
    pdf_bytes = populate_pdf("./data/form_fillable.pdf", schema, answers)

    out_path = Path("./output/pdf_populated.pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(pdf_bytes)


if __name__ == "__main__":
    main()
