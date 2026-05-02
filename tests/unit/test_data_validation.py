"""Validation helpers."""

from medical_form_automation.data_validation import (
    run_validations,
    validate_area_code,
    validate_dob,
)


def test_validate_dob_accepts_realistic_date() -> None:
    result = validate_dob("15", "04", "1960")
    assert result["valid"] is True
    assert result["age"] >= 60


def test_validate_dob_rejects_future() -> None:
    result = validate_dob("01", "01", "9999")
    assert result["valid"] is False


def test_validate_dob_rejects_garbage() -> None:
    result = validate_dob("xx", "yy", "zz")
    assert result["valid"] is False


def test_validate_area_code_real_us_code() -> None:
    # 212 = New York
    assert validate_area_code("1", "212") not in ("Invalid Area Code", "Error", "Invalid Format")


def test_validate_area_code_invalid() -> None:
    assert validate_area_code("1", "000") in ("Invalid Area Code", "Error", "Invalid Format", "")


def test_run_validations_clean_answers() -> None:
    answers = {
        "areacode": {"value": "613"},
        "phonea": {"value": "656"},
        "phoneb": {"value": "5890"},
        "areacode1": {"value": "647"},
        "phonea1": {"value": "666"},
        "phoneb1": {"value": "8888"},
        "date_of_birth_d": {"value": "15"},
        "date_of_birth_m": {"value": "04"},
        "date_of_birth_y": {"value": "1960"},
    }
    errors = run_validations(answers)
    assert errors == []


def test_run_validations_catches_bad_phone() -> None:
    answers = {"phonea": {"value": "12"}}  # only 2 digits
    errors = run_validations(answers)
    assert any(e["field"] == "phonea" for e in errors)


def test_run_validations_skips_null_dates() -> None:
    answers = {
        "date_last_d": {"value": None},
        "date_last_m": {"value": None},
        "date_last_y": {"value": None},
    }
    errors = run_validations(answers)
    assert errors == []
