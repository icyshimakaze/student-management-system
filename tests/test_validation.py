import pytest

from validation import ValidationError, credits, email, grade, identifier, name, required


@pytest.mark.parametrize("value", [None, "", "   "])
def test_required_rejects_blank_value(value):
    with pytest.raises(ValidationError):
        required(value, "Name")


@pytest.mark.parametrize("value", ["no-at-sign", "person@", "@example.com"])
def test_email_rejects_invalid_addresses(value):
    with pytest.raises(ValidationError):
        email(value)


def test_email_normalizes_case_and_whitespace():
    assert email(" Person@Example.edu ") == "person@example.edu"


@pytest.mark.parametrize("value", [0, 7, "abc"])
def test_credits_reject_invalid_values(value):
    with pytest.raises(ValidationError):
        credits(value)


@pytest.mark.parametrize("value", [-1, 101, "abc"])
def test_grade_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        grade(value)


def test_identifier_allows_common_database_codes():
    assert identifier("STU-0001", "Student ID") == "STU-0001"
    assert identifier("EE_101", "Course code") == "EE_101"


@pytest.mark.parametrize("value", ["ab", "hello world!", "", None])
def test_identifier_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        identifier(value, "Course code")


def test_name_accepts_normal_human_name():
    assert name("Mary Jane", "First name") == "Mary Jane"
