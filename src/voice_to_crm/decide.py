from datetime import date

from voice_to_crm.models import Decision, Extraction
from voice_to_crm.normalize import is_valid_email, normalize_phone


def decision(extraction: Extraction, reference_date: date) -> Decision:
    task_payloads = [task.model_dump() for task in extraction.tasks]

    # Rule 1: no lead -> NO_LEAD (tasks are still kept)
    if extraction.lead is None:
        return Decision(outcome="NO_LEAD", task_payloads=task_payloads)

    lead = extraction.lead
    lead_payload = lead.model_dump()
    reasons: list[str] = []
    warnings: list[str] = []

    # Rule 2: last_name is required; company falls back to a default
    if lead.last_name is None:
        reasons.append("missing: last_name")
    elif lead.company is None:
        lead_payload["company"] = f"Private Investor - {lead.last_name}"
        warnings.append("defaulted: company")

    # Rule 3: anything Claude flagged as uncertain needs a human look
    for path in extraction.uncertain_fields:
        reasons.append(f"uncertain: {path}")

    # Rule 4: validation (a missing value is fine; a present-but-bad one is not)
    if lead.email is not None and not is_valid_email(lead.email):
        reasons.append("invalid: lead.email")
    if lead.phone is not None:
        phone = normalize_phone(lead.phone)
        if phone is None or len(phone) < 10:
            reasons.append("invalid: lead.phone")
        else:
            lead_payload["phone"] = phone
    for i, task in enumerate(extraction.tasks):
        if task.due_date is None:
            continue
        try:
            due = date.fromisoformat(task.due_date)
        except ValueError:
            reasons.append(f"invalid: tasks[{i}].due_date")
            continue
        if due < reference_date:
            reasons.append(f"invalid: tasks[{i}].due_date (past)")

    # Rule 5: any reason -> NEEDS_REVIEW, otherwise CREATE
    outcome = "NEEDS_REVIEW" if reasons else "CREATE"

    return Decision(
        outcome=outcome,
        reasons=reasons,
        warnings=warnings,
        lead_payload=lead_payload,
        task_payloads=task_payloads,
    )
