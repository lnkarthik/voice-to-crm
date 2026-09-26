# Extraction Schema — Draft

> Scratch notes; folds into the spec later.
> Scoring options: `exact` · `normalized` (say how: lowercase, digits-only, …) · `not scored`
>
> Naming: the extraction schema uses `snake_case`. It is NOT the Salesforce payload;
> code maps each field to its Salesforce API name (right-hand column).

## 1. Lead

### Extracted by Claude

| Field | Type | Required? | Salesforce field | How to score |
|-------|------|-----------|------------------|--------------|
| first_name | string | no | FirstName | normalized: trim + casefold, then exact |
| last_name | string | **yes** | LastName | normalized: trim + casefold, then exact |
| company | string, or null if not said | **yes** (Salesforce) | Company | normalized: casefold, strip punctuation and suffixes (Inc, LLC, Ltd, Corp), then exact. Scored on Claude's raw output (null vs null), *before* the default below |
| title | string | no | Title | not scored in headline numbers ("VP Ops" vs "VP of Operations") |
| email | string | no | Email | normalized: trim + lowercase, then exact |
| phone | string | no | Phone | normalized: digits only, compare last 10 digits |
| rating | picklist: Hot / Warm / Cold | no | Rating | exact |
| description | string (1–3 sentence summary) | no | Description | not scored |

### Set by code (not extracted, not scored)

| Salesforce field | Value |
|------------------|-------|
| LeadSource | "Other" (configurable; Salesforce's default picklist has no "Voice Memo") |
| Status | "Open - Not Contacted" |
| OwnerId | the logged-in `sf` CLI user (Salesforce default) |
| Company (only when Claude returned null) | `Private Investor - <last_name>` (e.g. `Private Investor - Allen`), and Description is prefixed with `[Company defaulted: none mentioned]` |

## 2. Task

### Extracted by Claude (0..N per memo)

| Field | Type | Required? | Salesforce field | How to score |
|-------|------|-----------|------------------|--------------|
| task_type | picklist: Call / Email / Meeting / Other | yes | TaskSubtype: Call→"Call", Email→"Email", Meeting/Other→"Task" (mapped by code) | exact |
| subject | string ("Send pricing deck to Priya") | yes | Subject | not scored in headline numbers |
| due_phrase | string, the words spoken ("by Friday") | no | (none; kept for debugging) | not scored |
| due_date | date `YYYY-MM-DD`, or null | no | ActivityDate | exact |
| priority | picklist: High / Normal / Low, or null | no | Priority | exact (null → code sets "Normal") |

### Set by code (not extracted, not scored)

| Salesforce field | Value |
|------------------|-------|
| Status | "Not Started" |
| WhoId | Id of the Lead created from the same memo (null for NO_LEAD) |
| OwnerId | the logged-in `sf` CLI user |

### Due dates
- Output **both**: `due_phrase` (what was said) and `due_date` (the resolved date).
- **Claude resolves** the date, because phrases like "the Tuesday after next" or
  "end of the month" are hard for rule-based parsers.
- Resolving needs a **reference date**: the memo's recorded timestamp (plus weekday)
  is passed in the prompt. Without it, "Friday" is ambiguous.
- Code validates the result: it must be a real date, and on or after the reference date.
  Otherwise the Task is flagged for review.

### Scoring note
Tasks are a *list*, so predicted Tasks must first be **matched** to gold Tasks
(e.g. by task_type + due_date, then subject similarity) before fields can be scored.
Unmatched predictions count as false positives; unmatched gold Tasks as false negatives.

## 3. Abstention

### Output shape
```json
{
  "lead": { ... } | null,
  "tasks": [ ... ],
  "uncertain_fields": ["lead.phone", "tasks[0].due_date"]
}
```

- **No lead in this memo** → `"lead": null`. `tasks` may still be non-empty
  (a reminder to yourself) or empty (nothing actionable).
- **Not mentioned** → the field is `null`. Claude must never invent a value.
- **Mentioned but unclear** (garbled, partly heard, contradictory) → Claude puts its
  **best guess** in the field AND lists the field's path in `uncertain_fields`.
  So `null` means "not said", and `uncertain_fields` means "said, but don't trust it".
  The two can't be confused.

### Who decides CREATE / NEEDS_REVIEW / NO_LEAD?
**The validation code, not Claude.** Claude only reports what it heard; deterministic
Python applies the rules, so decisions are testable and explainable.

Rules, applied in order:
1. `lead` is null → **NO_LEAD** (any tasks are created without a WhoId).
2. `last_name` is null → **NEEDS_REVIEW** (Salesforce requires it; no safe default).
   `company` is null → code fills `Private Investor - <last_name>` and continues
   (the memo can still be CREATE). Recorded as a **warning**, not a review reason.
3. Anything in `uncertain_fields` → **NEEDS_REVIEW**.
4. Validation fails (bad email format, phone with < 10 digits, due_date in the past or
   not a real date) → **NEEDS_REVIEW**.
5. Otherwise → **CREATE**.

Each NEEDS_REVIEW carries a list of **reasons** (e.g. `"missing: last_name"`,
`"uncertain: lead.phone"`) so the web UI can highlight exactly what to fix.
Any decision can also carry **warnings** (e.g. `"defaulted: company"`), shown in the UI but
not blocking.

### How abstention is scored
Every gold memo is labeled with its expected decision. We report:
- **Decision accuracy**: % of memos where the predicted decision matches the gold one.
- **Review precision**: of memos sent to NEEDS_REVIEW, how many truly needed it
  (low = pipeline is annoying).
- **Review recall**: of memos that truly needed review, how many were caught
  (low = pipeline pushes bad data into Salesforce; the costlier error).

## 4. Examples

> Reference date for all examples: **Monday 2026-09-28** (the memo's recorded time).
> Speaker convention (v1): every memo is dictated by **the salesperson** ("I" = the salesperson).
> Domain: commercial real estate.

### 4a. Clean memo → CREATE
**Speech:** "Just got off a call with Maria Lopez, she's director of real estate at Sunbelt
Retail Group. They want about twenty thousand square feet on US-75 with at least fifty
parking spots and they're ready to sign this quarter, so this one's hot. Her email is
maria.lopez@sunbeltretail.com, phone 214-555-0147. I need to email her three listings by
Friday, high priority, and set up a site tour for Wednesday October 7th."

```json
{
  "lead": {
    "first_name": "Maria",
    "last_name": "Lopez",
    "company": "Sunbelt Retail Group",
    "title": "Director of Real Estate",
    "email": "maria.lopez@sunbeltretail.com",
    "phone": "214-555-0147",
    "rating": "Hot",
    "description": "Wants ~20,000 sq ft on US-75 with 50+ parking spots; ready to sign this quarter."
  },
  "tasks": [
    {
      "task_type": "Email",
      "subject": "Email Maria three US-75 listings",
      "due_phrase": "by Friday",
      "due_date": "2026-10-02",
      "priority": "High"
    },
    {
      "task_type": "Meeting",
      "subject": "Site tour with Maria Lopez",
      "due_phrase": "Wednesday October 7th",
      "due_date": "2026-10-07",
      "priority": null
    }
  ],
  "uncertain_fields": []
}
```
**Decision:** CREATE — Lead + 2 Tasks linked to it (WhoId).

### 4b. Missing company → CREATE with default company
**Speech:** "Got a voicemail from Barry Allen. He's looking to lease a property on US-75 to build
a retail store, needs at least fifty parking spots. Didn't say what company he's with. Call him
back if anything comes up, his number is 123-456-7890 and email is test@gmail.com."

```json
{
  "lead": {
    "first_name": "Barry",
    "last_name": "Allen",
    "company": null,
    "title": null,
    "email": "test@gmail.com",
    "phone": "123-456-7890",
    "rating": null,
    "description": "Looking to lease property on US-75 to build a retail store; needs 50+ parking spots."
  },
  "tasks": [
    {
      "task_type": "Call",
      "subject": "Call Barry Allen back about US-75 retail lease",
      "due_phrase": null,
      "due_date": null,
      "priority": null
    }
  ],
  "uncertain_fields": []
}
```
**Decision:** CREATE — warnings: `["defaulted: company"]`. Code sets Company to
`Private Investor - Allen` before pushing; Claude's output above stays `null`.

### 4c. Missing last name + garbled email → NEEDS_REVIEW
**Speech:** "Met a guy named Tony at the retail meetup, runs Lakeside Pizza, wants a second
location near the Galleria. Email is tony at lakeside... pizza... something dot com, I didn't
catch it all. Call him Thursday."

```json
{
  "lead": {
    "first_name": "Tony",
    "last_name": null,
    "company": "Lakeside Pizza",
    "title": null,
    "email": "tony@lakesidepizza.com",
    "phone": null,
    "rating": null,
    "description": "Owns Lakeside Pizza; wants a second location near the Galleria. Met at retail meetup."
  },
  "tasks": [
    {
      "task_type": "Call",
      "subject": "Call Tony (Lakeside Pizza) about second location",
      "due_phrase": "Thursday",
      "due_date": "2026-10-01",
      "priority": null
    }
  ],
  "uncertain_fields": ["lead.email"]
}
```
**Decision:** NEEDS_REVIEW — reasons: `["missing: last_name", "uncertain: lead.email"]`.

### 4d. No lead, reminder only → NO_LEAD
**Speech:** "Note to self: tomorrow morning I need to chase the signed lease paperwork for the
Plano deal. High priority."

```json
{
  "lead": null,
  "tasks": [
    {
      "task_type": "Other",
      "subject": "Chase signed lease paperwork for the Plano deal",
      "due_phrase": "tomorrow morning",
      "due_date": "2026-09-29",
      "priority": "High"
    }
  ],
  "uncertain_fields": []
}
```
**Decision:** NO_LEAD — 1 Task created with no WhoId.
