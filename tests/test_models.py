import pytest
from conftest import load_example
from pydantic import ValidationError

from voice_to_crm.models import Extraction, LeadDraft, TaskDraft


def test_all_examples_parse():
    for name in ["4a_create", "4b_default_company", "4c_needs_review", "4d_no_lead"]:
        Extraction.model_validate(load_example(name))


def test_no_lead_example_has_null_lead():
    assert Extraction.model_validate(load_example("4d_no_lead")).lead is None


def test_picklists_are_case_insensitive():
    lead = LeadDraft(last_name="Lopez", rating="hot")
    task = TaskDraft(task_type="call", subject="x", priority="HIGH")
    assert (lead.rating, task.task_type, task.priority) == ("Hot", "Call", "High")


def test_blank_strings_become_none():
    assert LeadDraft(last_name="  ", email="").last_name is None


def test_impossible_date_still_parses():
    assert (
        TaskDraft(task_type="Call", subject="x", due_date="2026-02-30").due_date
        == "2026-02-30"
    )


def test_unknown_picklist_value_rejected():
    with pytest.raises(ValidationError):
        LeadDraft(rating="Lukewarm")
