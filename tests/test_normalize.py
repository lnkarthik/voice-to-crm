import pytest

from voice_to_crm.normalize import (
    is_valid_email,
    normalize_company,
    normalize_email,
    normalize_name,
    normalize_phone,
)


@pytest.mark.parametrize("raw,expected", [(" Lopez ", "lopez"), ("LÓPEZ", "lópez")])
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    "raw", ["Acme, Inc.", "ACME LLC", "Acme Corp", "acme ltd", "Acme"]
)
def test_normalize_company_strips_suffixes(raw):
    assert normalize_company(raw) == "acme"


def test_normalize_company_multiword():
    assert normalize_company("Sunbelt Retail Group") == "sunbelt retail group"


def test_normalize_email():
    assert (
        normalize_email(" Maria.Lopez@SunbeltRetail.com ")
        == "maria.lopez@sunbeltretail.com"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "214-555-0147",
        "(214) 555-0147",
        "+1 (214) 555-0147",
        "1-214-555-0147",
        "214.555.0147",
    ],
)
def test_normalize_phone_last_10_digits(raw):
    assert normalize_phone(raw) == "2145550147"


def test_normalize_phone_short_keeps_digits():
    assert normalize_phone("555-0147") == "5550147"


def test_none_passthrough():
    for f in (normalize_name, normalize_company, normalize_email, normalize_phone):
        assert f(None) is None


@pytest.mark.parametrize(
    "value,ok",
    [
        ("a@b.co", True),
        ("maria.lopez@sunbeltretail.com", True),
        ("tony@lakeside", False),
        ("no-at-sign.com", False),
        ("a b@c.com", False),
    ],
)
def test_is_valid_email(value, ok):
    assert is_valid_email(value) is ok
