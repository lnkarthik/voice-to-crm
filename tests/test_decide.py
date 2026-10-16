from datetime import date

from conftest import load_example

from voice_to_crm.decide import decision
from voice_to_crm.models import Extraction

REFERENCE_DATE = date(2026, 9, 28)


def run(name: str):
    return decision(Extraction.model_validate(load_example(name)), REFERENCE_DATE)


def test_clean_memo_is_create():
    result = run("4a_create")
    assert result.outcome == "CREATE"
    assert result.reasons == []
    assert result.warnings == []
    assert result.lead_payload["company"] == "Sunbelt Retail Group"
    assert len(result.task_payloads) == 2


def test_missing_company_is_defaulted_with_warning():
    result = run("4b_default_company")
    assert result.outcome == "CREATE"
    assert result.reasons == []
    assert result.warnings == ["defaulted: company"]
    assert result.lead_payload["company"] == "Private Investor - Allen"


def test_missing_last_name_needs_review():
    result = run("4c_needs_review")
    assert result.outcome == "NEEDS_REVIEW"
    assert "missing: last_name" in result.reasons


def test_missing_last_name_and_company_does_not_crash():
    extraction = Extraction.model_validate({"lead": {"first_name": "Tony"}})
    result = decision(extraction, REFERENCE_DATE)
    assert result.outcome == "NEEDS_REVIEW"
    assert result.warnings == []
    assert result.lead_payload["company"] is None


def test_no_lead_keeps_tasks():
    result = run("4d_no_lead")
    assert result.outcome == "NO_LEAD"
    assert result.lead_payload is None
    assert len(result.task_payloads) == 1


def test_no_lead_and_no_tasks():
    result = decision(Extraction(), REFERENCE_DATE)
    assert result.outcome == "NO_LEAD"
    assert result.task_payloads == []


def test_extracted_company_is_not_overwritten():
    extraction = Extraction.model_validate(
        {"lead": {"last_name": "Lopez", "company": "Sunbelt"}}
    )
    result = decision(extraction, REFERENCE_DATE)
    assert result.lead_payload["company"] == "Sunbelt"
    assert result.warnings == []


def test_input_extraction_is_not_mutated():
    extraction = Extraction.model_validate(load_example("4b_default_company"))
    decision(extraction, REFERENCE_DATE)
    assert extraction.lead.company is None


def test_uncertain_fields_become_reasons():
    result = run("4c_needs_review")
    assert result.reasons == ["missing: last_name", "uncertain: lead.email"]


def test_uncertain_field_alone_forces_review():
    extraction = Extraction.model_validate(
        {
            "lead": {"last_name": "Lopez", "company": "Sunbelt"},
            "uncertain_fields": ["lead.phone"],
        }
    )
    result = decision(extraction, REFERENCE_DATE)
    assert result.outcome == "NEEDS_REVIEW"
    assert result.reasons == ["uncertain: lead.phone"]


def review_reasons(lead_extra: dict | None = None, tasks: list | None = None):
    lead = {"last_name": "Lopez", "company": "Sunbelt", **(lead_extra or {})}
    extraction = Extraction.model_validate({"lead": lead, "tasks": tasks or []})
    return decision(extraction, REFERENCE_DATE)


def task(due_date: str | None) -> dict:
    return {"task_type": "Call", "subject": "x", "due_date": due_date}


def test_bad_email_needs_review():
    result = review_reasons({"email": "tony at lakeside"})
    assert result.outcome == "NEEDS_REVIEW"
    assert result.reasons == ["invalid: lead.email"]


def test_short_phone_needs_review():
    result = review_reasons({"phone": "555-0147"})
    assert result.outcome == "NEEDS_REVIEW"
    assert result.reasons == ["invalid: lead.phone"]


def test_valid_phone_is_normalized_in_payload():
    result = review_reasons({"phone": "(555) 014-7890"})
    assert result.outcome == "CREATE"
    assert result.lead_payload["phone"] == "5550147890"


def test_invalid_phone_keeps_raw_value_in_payload():
    result = review_reasons({"phone": "555-0147"})
    assert result.outcome == "NEEDS_REVIEW"
    assert result.lead_payload["phone"] == "555-0147"


def test_phone_without_digits_needs_review():
    assert review_reasons({"phone": "call me"}).reasons == ["invalid: lead.phone"]


def test_missing_email_and_phone_are_fine():
    assert review_reasons().outcome == "CREATE"


def test_impossible_due_date_needs_review():
    result = review_reasons(tasks=[task("2026-02-30")])
    assert result.outcome == "NEEDS_REVIEW"
    assert result.reasons == ["invalid: tasks[0].due_date"]


def test_past_due_date_needs_review():
    result = review_reasons(tasks=[task("2026-09-27")])
    assert result.reasons == ["invalid: tasks[0].due_date (past)"]


def test_due_date_on_reference_date_is_ok():
    assert review_reasons(tasks=[task("2026-09-28")]).outcome == "CREATE"


def test_null_due_date_is_ok():
    assert review_reasons(tasks=[task(None)]).outcome == "CREATE"


def test_reason_names_the_bad_task_index():
    result = review_reasons(tasks=[task("2026-10-01"), task("2026-01-01")])
    assert result.reasons == ["invalid: tasks[1].due_date (past)"]


def test_multiple_problems_are_all_reported():
    result = review_reasons({"email": "nope", "phone": "123"}, tasks=[task("bad")])
    assert result.reasons == [
        "invalid: lead.email",
        "invalid: lead.phone",
        "invalid: tasks[0].due_date",
    ]
