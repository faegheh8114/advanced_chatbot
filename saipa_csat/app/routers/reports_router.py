import datetime as dt
from calendar import monthrange

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from .. import models
from ..auth import require_user
from .. import analytics
from ..corrective_actions import generate_suggestions

router = APIRouter(prefix="/reports")
templates = Jinja2Templates(directory="app/templates")

UNRESOLVED = ["حل نشد", "نیازمند اقدام بیشتر", "مشتری پاسخ نداد"]


@router.get("")
def monthly_report(request: Request, year_month: str = "", db: Session = Depends(get_db), user=Depends(require_user)):
    if not year_month:
        year_month = dt.date.today().strftime("%Y-%m")
    year, month = (int(x) for x in year_month.split("-"))
    date_from = dt.date(year, month, 1)
    date_to = dt.date(year, month, monthrange(year, month)[1])

    surveys = db.execute(
        select(models.Survey).where(
            models.Survey.source == "direct_call",
            models.Survey.survey_date >= date_from,
            models.Survey.survey_date <= date_to,
        )
    ).scalars().all()

    overview = analytics.overview_metrics(db, surveys)
    reasons = analytics.dissatisfaction_reasons(db)
    lowest = analytics.lowest_scoring_questions(db, top_n=5, date_from=date_from, date_to=date_to)

    company_months = [r[0] for r in db.execute(select(models.MonthlyCompanyResult.year_month).distinct()).all()]
    comparison = analytics.company_vs_dealership(db, year_month) if year_month in company_months else None

    open_actions = db.execute(
        select(models.CorrectiveAction).where(models.CorrectiveAction.status.in_(["در حال بررسی", "در حال اجرا"]))
    ).scalars().all()
    completed_actions = db.execute(
        select(models.CorrectiveAction).where(models.CorrectiveAction.status == "تکمیل شده")
    ).scalars().all()
    action_results = [{"action": a, "effect": analytics.action_effectiveness(a)} for a in completed_actions]

    unresolved = db.execute(
        select(models.InternalFollowUp).where(models.InternalFollowUp.followup_result.in_(UNRESOLVED))
    ).scalars().all()

    recommendations = generate_suggestions(db, top_n=3)

    return templates.TemplateResponse(
        "monthly_report.html",
        {
            "request": request, "user": user, "year_month": year_month,
            "overview": overview, "reasons": reasons, "lowest": lowest, "comparison": comparison,
            "open_actions": open_actions, "action_results": action_results, "unresolved": unresolved,
            "recommendations": recommendations,
        },
    )
