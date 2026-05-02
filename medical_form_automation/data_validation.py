"""Validate extracted field values (phones, area codes, DOBs, postal codes)."""

from datetime import date
from typing import Any

import pgeocode
import phonenumbers
import usaddress
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from phonenumbers import geocoder

_us = pgeocode.Nominatim("us")
_ca = pgeocode.Nominatim("ca")


def validate_address(
    postal_code: str, state_province: str, country: str = "auto"
) -> dict[str, Any]:
    if country == "auto":
        country = "ca" if any(c.isalpha() for c in postal_code) else "us"

    geo = _us if country.lower() == "us" else _ca
    result = geo.query_postal_code(postal_code)

    if result.empty or str(result["state_code"]) == "nan":
        return {"valid": False, "error": "Invalid postal code", "outcome": False}

    matches = result["state_code"] == state_province.upper()
    return {
        "valid": bool(matches),
        "postal_code": postal_code,
        "expected_state": result["state_code"],
        "provided_state": state_province.upper(),
        "city": result["place_name"],
        "country": country.upper(),
        "outcome": True,
    }


def parse_address(address_str: str) -> dict[str, Any]:
    parts, _type = usaddress.tag(address_str)
    return validate_address(parts["ZipCode"], parts["StateName"], country="auto")


def validate_dob(
    date_of_birth_d: str | int,
    date_of_birth_m: str | int,
    date_of_birth_y: str | int,
    min_age: int = 0,
    max_age: int = 150,
) -> dict[str, Any]:
    try:
        dob = parse(f"{date_of_birth_y}-{date_of_birth_m}-{date_of_birth_d}").date()
        today = date.today()

        if dob > today:
            return {"valid": False, "error": "Future date"}

        age = relativedelta(today, dob).years
        if not (min_age <= age <= max_age):
            return {"valid": False, "error": f"Age {age} out of range ({min_age}-{max_age})"}

        return {"valid": True, "date": dob, "age": age}
    except Exception:
        return {"valid": False, "error": "Invalid date"}


def validate_area_code(country_code: str, area_code: str) -> str:
    test_number = f"+{country_code}{area_code}5551212"
    try:
        parsed_num = phonenumbers.parse(test_number)
        if phonenumbers.is_possible_number(parsed_num):
            location = geocoder.description_for_number(parsed_num, "en")
            return location if location else "Invalid Area Code"
        return "Invalid Format"
    except Exception:
        return "Error"


def run_validations(answers: dict[str, Any]) -> list[dict[str, Any]]:
    """Run all field validations on an extracted-answers dict.

    Returns a list of validation errors (empty list = all valid). Does not raise —
    callers decide whether to escalate to a 4xx response.
    """
    errors: list[dict[str, Any]] = []

    def _value(key: str) -> Any:
        entry = answers.get(key)
        if isinstance(entry, dict):
            return entry.get("value")
        return entry

    def _is_valid_three(v: Any) -> bool:
        return isinstance(v, str) and len(v) == 3 and v.isdecimal()

    def _is_valid_four(v: Any) -> bool:
        return isinstance(v, str) and len(v) == 4 and v.isdecimal()

    for ac_key in ("areacode", "areacode1"):
        v = _value(ac_key)
        if v in (None, "null"):
            continue
        result = validate_area_code("1", str(v))
        if result in ("Invalid area code", "Error", "Invalid Format", "Invalid Area Code"):
            errors.append({"field": ac_key, "value": v, "error": f"Invalid area code: {result}"})

    for first_key in ("phonea", "phonea1"):
        v = _value(first_key)
        if v in (None, "null"):
            continue
        if not _is_valid_three(v):
            errors.append({"field": first_key, "value": v, "error": "Expected 3 digits"})

    for last_key in ("phoneb", "phoneb1"):
        v = _value(last_key)
        if v in (None, "null"):
            continue
        if not _is_valid_four(v):
            errors.append({"field": last_key, "value": v, "error": "Expected 4 digits"})

    date_groups = [
        ("date_of_birth_d", "date_of_birth_m", "date_of_birth_y"),
        ("date_last_d", "date_last_m", "date_last_y"),
        ("date_return_d", "date_return_m", "date_return_y"),
        ("date_childbirth_d", "date_childbirth_m", "date_childbirth_y"),
    ]
    for d_key, m_key, y_key in date_groups:
        d, m, y = _value(d_key), _value(m_key), _value(y_key)
        if d in (None, "null") or m in (None, "null") or y in (None, "null"):
            continue
        result = validate_dob(d, m, y)
        if not result.get("valid"):
            errors.append(
                {"field": f"{d_key}/{m_key}/{y_key}", "value": f"{y}-{m}-{d}", "error": result.get("error")}
            )

    return errors
