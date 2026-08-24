import datetime as dt

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from .. import models
from ..auth import require_user, require_admin
from .. import analytics
from ..question_bank import SCORE_QUESTION_CODES, QUESTION_BY_CODE

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/comparison")
def comparison_page(request: Request, year_month: str = "", db: Session = Depends(get_db), user=Depends(require_user)):
    months = [r[0] for r in db.execute(
        select(models.MonthlyCompanyResult.year_month).distinct().order_by(models.MonthlyCompanyResult.year_month.desc())
    ).all()]
    if not year_month:
        year_month = months[0] if months else dt.date.today().strftime("%Y-%m")

    data = analytics.company_vs_dealership(db, year_month) if year_month in months else None

    trend_rows = []
    for ym in sorted(months):
        d = analytics.company_vs_dealership(db, ym)
        trend_rows.append({
            "month": ym,
            "company_csi": next((r["company"] for r in d["rows"] if r["code"] is None), None),
            "dealership_csi": next((r["dealership"] for r in d["rows"] if r["code"] is None), None),
        })

    return templates.TemplateResponse(
        "comparison.html",
        {"request": request, "user": user, "months": months, "year_month": year_month, "data": data, "trend_rows": trend_rows},
    )


@router.get("/comparison/company-result/new")
def new_company_result_form(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse(
        "company_result_form.html",
        {"request": request, "user": user, "questions": SCORE_QUESTION_CODES, "QUESTION_BY_CODE": QUESTION_BY_CODE},
    )


@router.post("/comparison/company-result/new")
async def create_company_result(request: Request, db: Session = Depends(get_db), user=Depends(require_admin)):
    form = await request.form()
    year_month = form["year_month"]

    def upsert(question_code, csi=None, csat=None, score=None):
        existing = db.execute(
            select(models.MonthlyCompanyResult).where(
                models.MonthlyCompanyResult.year_month == year_month,
                models.MonthlyCompanyResult.question_code == question_code,
            )
        ).scalars().first()
        if existing:
            if csi is not None: existing.csi = csi
            if csat is not None: existing.csat = csat
            if score is not None: existing.score = score
        else:
            db.add(models.MonthlyCompanyResult(
                year_month=year_month, question_code=question_code, csi=csi, csat=csat, score=score,
                created_by=user.id,
            ))

    csi = form.get("csi")
    csat = form.get("csat")
    upsert(None, csi=float(csi) if csi else None, csat=float(csat) if csat else None)

    for code in SCORE_QUESTION_CODES:
        val = form.get(f"score_{code}")
        if val:
            upsert(code, score=float(val))

    db.commit()
    return RedirectResponse(f"/comparison?year_month={year_month}", status_code=303)
