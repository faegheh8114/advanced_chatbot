import datetime as dt

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from .. import models
from ..auth import require_user
from ..analytics import compute_csi_csat
from ..question_bank import (
    OFFICIAL_QUESTIONS, QUESTION_BY_CODE, SCORE_0_10, TEXT, CHOICE, YES_NO, DATETIME,
    LOW_SCORE_THRESHOLD, DISSATISFACTION_REASONS, CORRECTIVE_ACTION_TYPES, FOLLOWUP_RESULT_STATUSES,
    QUESTION_TO_REASON,
)

router = APIRouter(prefix="/surveys")
templates = Jinja2Templates(directory="app/templates")


@router.get("/new")
def new_survey(request: Request, customer_id: int, db: Session = Depends(get_db), user=Depends(require_user)):
    customer = db.get(models.Customer, customer_id)
    return templates.TemplateResponse(
        "survey_wizard.html",
        {
            "request": request, "customer": customer, "user": user,
            "questions": OFFICIAL_QUESTIONS,
            "SCORE_0_10": SCORE_0_10, "TEXT": TEXT, "CHOICE": CHOICE, "YES_NO": YES_NO, "DATETIME": DATETIME,
            "today": dt.date.today().isoformat(),
        },
    )


def _parse_bool(v: str | None) -> bool | None:
    if v is None or v == "":
        return None
    return v == "yes"


@router.post("/new")
async def create_survey(request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    form = await request.form()
    customer_id = int(form["customer_id"])
    survey_date_raw = form.get("survey_date") or dt.date.today().isoformat()
    survey_date = dt.date.fromisoformat(survey_date_raw)

    dealership = db.execute(select(models.Dealership)).scalars().first()

    survey = models.Survey(
        customer_id=customer_id,
        dealership_id=dealership.id,
        staff_id=user.id,
        survey_date=survey_date,
        source="direct_call",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(survey)
    db.flush()

    score_values: dict[str, float] = {}

    for q in OFFICIAL_QUESTIONS:
        field = f"q_{q.code}"
        raw = form.get(field)

        if q.conditional_on:
            parent_raw = form.get(f"q_{q.conditional_on}")
            parent_val = _parse_bool(parent_raw)
            if parent_val is not True:
                continue  # skip storing conditional answers when not applicable

        if raw is None or raw == "":
            continue

        answer = models.SurveyAnswer(survey_id=survey.id, question_code=q.code)
        if q.qtype == SCORE_0_10:
            val = float(raw)
            val = max(0.0, min(10.0, val))
            answer.value_numeric = val
            score_values[q.code] = val
        elif q.qtype == YES_NO:
            answer.value_bool = _parse_bool(raw)
        elif q.qtype == CHOICE:
            answer.value_text = raw
        elif q.qtype == DATETIME:
            try:
                answer.value_datetime = dt.datetime.fromisoformat(raw)
            except ValueError:
                continue
        elif q.qtype == TEXT:
            answer.value_text = raw
        db.add(answer)

    csi, csat = compute_csi_csat(score_values)
    survey.csi = csi
    survey.csat = csat
    survey.is_low_score = any(v < LOW_SCORE_THRESHOLD for v in score_values.values())

    # Optional demographic updates captured during the call
    customer = db.get(models.Customer, customer_id)
    for field, attr in (("gender", "gender"), ("age", "age"), ("education", "education"), ("job", "job")):
        val = form.get(field)
        if val:
            setattr(customer, attr, int(val) if attr == "age" and val.isdigit() else val)

    db.commit()
    db.refresh(survey)

    if survey.is_low_score:
        return RedirectResponse(f"/surveys/{survey.id}/followup", status_code=303)
    return RedirectResponse(f"/surveys/{survey.id}", status_code=303)


@router.get("/{survey_id}")
def survey_detail(survey_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    survey = db.get(models.Survey, survey_id)
    answers = {a.question_code: a for a in survey.answers}
    return templates.TemplateResponse(
        "survey_detail.html",
        {
            "request": request, "survey": survey, "answers": answers, "user": user,
            "questions": OFFICIAL_QUESTIONS, "QUESTION_BY_CODE": QUESTION_BY_CODE,
        },
    )


@router.get("/{survey_id}/followup")
def followup_form(survey_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    survey = db.get(models.Survey, survey_id)
    scores = {a.question_code: a.value_numeric for a in survey.answers if a.value_numeric is not None}
    low_questions = [
        {"code": c, "label": QUESTION_BY_CODE[c].short_label, "value": v}
        for c, v in scores.items() if v < LOW_SCORE_THRESHOLD
    ]
    suggested_reason = None
    if low_questions:
        worst = min(low_questions, key=lambda x: x["value"])
        suggested_reason = QUESTION_TO_REASON.get(worst["code"])

    return templates.TemplateResponse(
        "internal_followup_form.html",
        {
            "request": request, "survey": survey, "low_questions": low_questions, "user": user,
            "reasons": DISSATISFACTION_REASONS, "action_types": CORRECTIVE_ACTION_TYPES,
            "result_statuses": FOLLOWUP_RESULT_STATUSES, "suggested_reason": suggested_reason,
            "today": dt.date.today().isoformat(),
        },
    )


@router.post("/{survey_id}/followup")
async def save_followup(survey_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    form = await request.form()
    existing = db.execute(
        select(models.InternalFollowUp).where(models.InternalFollowUp.survey_id == survey_id)
    ).scalars().first()
    fu = existing or models.InternalFollowUp(survey_id=survey_id, created_by=user.id)

    fu.main_reason = form.get("main_reason") or None
    fu.customer_explanation = form.get("customer_explanation") or None
    fu.is_actionable = _parse_bool(form.get("is_actionable"))
    fu.action_taken_type = form.get("action_taken_type") or None
    fu.action_description = form.get("action_description") or None
    fu.needs_followup = _parse_bool(form.get("needs_followup"))
    followup_date = form.get("followup_date")
    fu.followup_date = dt.date.fromisoformat(followup_date) if followup_date else None
    fu.followup_result = form.get("followup_result") or None
    followup_score = form.get("followup_score")
    fu.followup_score = float(followup_score) if followup_score else None
    fu.updated_by = user.id

    if not existing:
        db.add(fu)
    db.commit()
    return RedirectResponse(f"/surveys/{survey_id}", status_code=303)
