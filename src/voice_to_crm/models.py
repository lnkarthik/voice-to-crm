from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

Outcome = Literal["CREATE", "NEEDS_REVIEW", "NO_LEAD"]


def _canonical(v, allowed):
    if not isinstance(v, str):
        return v
    if not v.strip():
        return None
    for item in allowed:
        if item.lower() == v.strip().lower():
            return item
    return v


class LeadDraft(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    description: str | None = None
    rating: Literal["Hot", "Warm", "Cold"] | None = None

    @field_validator("first_name", "last_name", "company", "title", "email", "phone", "description", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("rating", mode="before")
    @classmethod
    def canonical_rating(cls, v):
        return _canonical(v, ["Hot", "Warm", "Cold"])


class TaskDraft(BaseModel):
    task_type: Literal["Call", "Email", "Meeting", "Other"]
    subject: str
    due_phrase: str | None = None
    due_date: str | None = None
    priority: Literal["High", "Normal", "Low"] | None = None

    @field_validator("due_date", "due_phrase", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("task_type", mode="before")
    @classmethod
    def canonical_task_type(cls, v):
        return _canonical(v, ["Call", "Email", "Meeting", "Other"])

    @field_validator("priority", mode="before")
    @classmethod
    def canonical_priority(cls, v):
        return _canonical(v, ["High", "Normal", "Low"])


class Extraction(BaseModel):
    lead: LeadDraft | None = None
    tasks: list[TaskDraft] = []
    uncertain_fields: list[str] = []


class Transcript(BaseModel):
    text: str
    reference_datetime: datetime
    source: str


class Decision(BaseModel):
    outcome: Outcome
    reasons: list[str] = []
    warnings: list[str] = []
    lead_payload: dict | None = None
    task_payloads: list[dict] = []

