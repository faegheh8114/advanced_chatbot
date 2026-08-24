import datetime as dt

from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from .. import models
from ..auth import require_user

router = APIRouter(prefix="/followups")
templates = Jinja2Templates(directory="app/templates")

UNRESOLVED = ["حل نشد", "نیازمند اقدام بیشتر", "مشتری پاسخ نداد"]


def _rows(db: Session):
    return db.execute(
        select(models.InternalFollowUp).join(models.Survey).order_by(models.InternalFollowUp.followup_date.asc().nulls_last())
    ).scalars().all()


@router.get("")
def followup_center(request: Request, db: Session = Depends(get_db), user=Depends(require_user)):
    today = dt.date.today()
    all_rows = _rows(db)

    due_today = [f for f in all_rows if f.needs_followup and f.followup_date == today and not f.followup_result]
    overdue = [f for f in all_rows if f.needs_followup and f.followup_date and f.followup_date < today and not f.followup_result]
    recently_dissatisfied = sorted(
        [f for f in all_rows if f.survey and f.survey.is_low_score],
        key=lambda f: f.survey.survey_date, reverse=True,
    )[:15]
    resolved = [f for f in all_rows if f.followup_result == "حل شد"]
    unresolved = [f for f in all_rows if f.followup_result in UNRESOLVED]

    return templates.TemplateResponse(
        "followup_center.html",
        {
            "request": request, "user": user,
            "due_today": due_today, "overdue": overdue, "recently_dissatisfied": recently_dissatisfied,
            "resolved": resolved, "unresolved": unresolved,
        },
    )
