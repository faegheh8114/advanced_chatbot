from collections import defaultdict

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from .. import models
from ..auth import require_user
from .. import analytics
from ..corrective_actions import generate_suggestions

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    surveys = db.execute(select(models.Survey).where(models.Survey.source == "direct_call")).scalars().all()

    overview = analytics.overview_metrics(db, surveys)
    trend = analytics.trend_over_time(surveys)
    question_avgs = analytics.question_averages(db)
    lowest = analytics.lowest_scoring_questions(db, top_n=6)
    reasons = analytics.dissatisfaction_reasons(db)
    correlations = analytics.correlation_insights(db)

    # customer segments (by gender) using each customer's most recent CSI
    segment_gender = defaultdict(list)
    segment_education = defaultdict(list)
    for s in surveys:
        if s.csi is None or not s.customer:
            continue
        segment_gender[s.customer.gender or "نامشخص"].append(s.csi)
        segment_education[s.customer.education or "نامشخص"].append(s.csi)

    def _avg_segment(d):
        return [{"key": k, "avg": round(sum(v) / len(v), 2), "n": len(v)} for k, v in d.items()]

    open_actions = db.execute(
        select(models.CorrectiveAction).where(models.CorrectiveAction.status.in_(["در حال بررسی", "در حال اجرا"]))
    ).scalars().all()
    completed_actions = db.execute(
        select(models.CorrectiveAction).where(models.CorrectiveAction.status == "تکمیل شده")
    ).scalars().all()
    action_results = [analytics.action_effectiveness(a) for a in completed_actions]
    improved = sum(1 for e in action_results if e["improvement"] is not None and e["improvement"] > 0)

    suggestions = generate_suggestions(db, top_n=3)

    latest_company_month = db.execute(
        select(models.MonthlyCompanyResult.year_month).distinct().order_by(models.MonthlyCompanyResult.year_month.desc())
    ).scalars().first()
    comparison = analytics.company_vs_dealership(db, latest_company_month) if latest_company_month else None

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request, "user": user,
            "overview": overview, "trend": trend, "question_avgs": question_avgs, "lowest": lowest,
            "reasons": reasons, "correlations": correlations,
            "segment_gender": _avg_segment(segment_gender), "segment_education": _avg_segment(segment_education),
            "open_actions_count": len(open_actions), "completed_actions_count": len(completed_actions),
            "improved_actions_count": improved, "suggestions": suggestions,
            "comparison": comparison, "latest_company_month": latest_company_month,
        },
    )
