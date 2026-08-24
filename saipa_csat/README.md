# سامانه رضایت مشتری — سایپا مشایخ کد ۳۲۹۹

Customer-satisfaction monitoring and corrective-action management system for
the Saipa Mashayekh dealership (code 3299). Staff collect satisfaction data
by phone using the company's **official** survey questions, the system
compares those results against the company's official monthly figures,
surfaces root causes, and turns findings into tracked corrective actions.

This is a standalone app in `saipa_csat/`, separate from the portfolio
chatbot at the repo root.

## Why this exists (product goal)

The app must answer, from real stored data, not generic statements:

1. How satisfied are our customers? 2. How do we compare with the company?
3. Where are we weaker? 4. Why are customers dissatisfied? 5. What repeats?
6. Who needs follow-up? 7. What should we do about it? 8. Who owns it?
9. By when? 10. Did it actually work?

## Architecture

```
saipa_csat/
├── app/
│   ├── main.py              FastAPI app, middleware, router registration, startup seed
│   ├── database.py          SQLAlchemy engine/session (SQLite dev, Postgres-ready via CSAT_DATABASE_URL)
│   ├── models.py            ORM models (see Data model below)
│   ├── question_bank.py     Official Q1-Q18 question bank — SOURCE OF TRUTH, never edited via UI
│   ├── auth.py               Password hashing + cookie-session auth + RBAC dependencies
│   ├── analytics.py         Deterministic analytics: CSI/CSAT, gaps, root-cause, correlations
│   ├── corrective_actions.py Data-grounded corrective-action suggestion generator
│   ├── importer.py          Excel import (validate/preview/commit) + export helpers
│   ├── seed.py               Idempotent demo data (admin/staff users, sample customers/surveys)
│   ├── routers/              One router per feature area (see API endpoints below)
│   ├── templates/            Jinja2, Persian/RTL
│   └── static/               CSS + vendored Chart.js (no CDN dependency)
├── requirements.txt
└── uploads/                  Uploaded Excel files awaiting preview/commit (gitignored)
```

### Design principles enforced in code

- **Official survey is immutable data, not configuration.** `question_bank.py`
  defines Q1–Q18 exactly as specified (wording, 0–10 scale, conditional
  logic for Q7→Q8 and Q9→Q9b/Q10). There is no admin UI to edit these.
- **Internal vs. official data are separate tables.** `SurveyAnswer` holds
  only official answers; `InternalFollowUp` (dissatisfaction reason, action
  taken, follow-up outcome) is a distinct table, populated only when a
  survey triggers the low-score flow, and is never merged into official
  survey scoring.
- **Company data is never overwritten automatically.** `MonthlyCompanyResult`
  rows are entered/imported by management and only change via explicit
  admin action.
- **Audit trail.** `created_at/updated_at/created_by/updated_by` on Survey,
  InternalFollowUp and CorrectiveAction.
- **No generic AI advice.** `corrective_actions.py` only ever produces
  recommendations built from real computed numbers (question averages,
  dissatisfaction-reason frequency) — see the Problem/Evidence/Root
  cause/Action/Owner/KPI structure required by the spec.

## Data model

`Dealership`, `User` (admin/staff), `Customer`, `OfficialQuestion` (DB mirror
of the question bank, for FK integrity), `Survey` (one call/visit; holds CSI,
CSAT, source = `direct_call` or `company_import`), `SurveyAnswer` (one row
per question per survey — numeric/text/bool/datetime typed columns, not a
JSON blob), `InternalFollowUp` (1:1 with a low-score Survey),
`CorrectiveAction` + `ActionFollowUp` (before/after KPI measurements),
`MonthlyCompanyResult` (official company figures per month, optionally per
question).

## CSI / CSAT formula (documented assumption)

The spec did not supply the company's exact published formula, so this is
made explicit and applied identically to dealership and company data so
comparisons are apples-to-apples:

- **CSI** = mean of all applicable official 0–10 questions marked
  `include_in_csi` in `question_bank.py` (Q1, Q3, Q4, Q6, Q8*, Q10*, Q11–Q17;
  *Q8/Q10 counted only for respondents to whom they apply — parts/cost
  questions).
- **CSAT** = `CSI × 10`, expressed as a percentage (matches the example in
  the spec: CSI 8.1 ↔ CSAT 81%).

Both are computed in `analytics.compute_csi_csat()` — the single place this
is defined.

## Key workflows

- **Call entry** (`/customers/new` → `/surveys/new`): staff pick/create a
  customer, then step through Q1–Q18 one at a time (official wording,
  0–10 scale UI) with conditional skip logic for Q8/Q9b/Q10. A score below
  6 on any core question marks the survey `is_low_score` and redirects to
  the **internal follow-up** form (`InternalFollowUp` — separate table).
- **Follow-up center** (`/followups`): due today / overdue / recently
  dissatisfied / resolved / unresolved, each row showing customer, issue,
  original score, action taken, staff, follow-up date, status, latest score.
- **Corrective actions** (`/actions`): manual entry or "turn into an
  action" from a data-grounded suggestion; tracks baseline → measurements →
  target, and reports whether the target was actually achieved.
- **Company comparison** (`/comparison`): per-question and overall gap table
  for a chosen month, largest negative/positive gaps, CSI trend chart.
- **Excel import** (`/import`, admin only): upload → auto-suggested column
  mapping (editable) → validation report (missing columns, out-of-range
  scores, bad dates, duplicates) → explicit commit. Rows that fail
  validation are skipped, never silently coerced.
- **Monthly report** (`/reports`): the 11 sections required by management,
  in plain language.

## API / page map

| Path | Purpose |
|---|---|
| `/login`, `/logout` | Auth |
| `/` | Management dashboard |
| `/customers`, `/customers/new`, `/customers/{id}` | Customer search/create/detail |
| `/surveys/new`, `/surveys/{id}`, `/surveys/{id}/followup` | Call wizard, survey detail, internal follow-up |
| `/followups` | Follow-up center |
| `/actions`, `/actions/new`, `/actions/{id}`, `/actions/{id}/measure` | Corrective action board |
| `/comparison`, `/comparison/company-result/new` | Company vs. dealership |
| `/import`, `/import/preview/{id}`, `/import/commit/{id}` | Excel import |
| `/export/surveys`, `/export/followups`, `/export/actions` | Excel export |
| `/reports` | Monthly management report |
| `/admin/users` | User management (admin only) |

## Running locally

```bash
cd saipa_csat
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8811
```

First run auto-creates the SQLite DB (`saipa_csat.db`) and seeds:

- Admin: `admin` / `admin123`
- Staff: `staff1` / `staff123`
- ~25 demo customers with call history, some flagged low-score with
  follow-ups, 3 months of demo company results, one example corrective
  action with a measurement history.

**Change both demo passwords before any real deployment.** Set
`CSAT_SECRET_KEY` (session signing) and `CSAT_DATABASE_URL` (e.g. a
`postgresql://...` URL) via environment variables in production —
the code is Postgres-ready without changes.

## What's deterministic vs. where AI could plug in later

Everything shipped is deterministic (pandas/NumPy correlations, rule-based
recommendation templates) — no LLM calls. The one documented place to add
an AI layer later, per the spec, is summarizing `Q18` free-text feedback and
`InternalFollowUp.customer_explanation` into clustered themes; any such
addition should keep citing the underlying survey/follow-up records it drew
from, never inventing numbers not present in the database.
