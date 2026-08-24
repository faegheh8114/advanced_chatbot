"""
Deterministic analytics engine.

No LLM / generative step here: every number is computed directly from stored
survey answers, internal follow-ups and corrective-action records. This module
is the single place that defines the CSI/CSAT formulas so they are applied
consistently everywhere in the app.

FORMULA NOTE (documented assumption, since the company did not supply an
exact published formula): CSI is the mean of all applicable official 0-10
satisfaction questions marked `include_in_csi` in question_bank.py (Q8/Q10
only counted for respondents to whom they apply). CSAT is expressed on the
same 0-100 scale as CSI*10 (this matches the example given in the product
spec: CSI 8.1 <-> CSAT 81%). Both are recomputed the same way for dealership
direct-call data and for official company data, so comparisons are apples to
apples.
"""
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .question_bank import (
    CSI_QUESTION_CODES, SCORE_QUESTION_CODES, QUESTION_BY_CODE, QUESTION_TO_REASON,
    LOW_SCORE_THRESHOLD,
)


def compute_csi_csat(answers: dict[str, float]) -> tuple[float | None, float | None]:
    """answers: {question_code: numeric value} for whichever score questions were answered
    (conditional questions like Q8/Q10 should simply be omitted when not applicable)."""
    values = [answers[c] for c in CSI_QUESTION_CODES if c in answers and answers[c] is not None]
    if not values:
        return None, None
    csi = round(sum(values) / len(values), 2)
    csat = round(csi * 10, 1)
    return csi, csat


def survey_answers_dict(survey: models.Survey) -> dict[str, dict]:
    out = {}
    for a in survey.answers:
        out[a.question_code] = {
            "numeric": a.value_numeric,
            "text": a.value_text,
            "bool": a.value_bool,
            "datetime": a.value_datetime,
        }
    return out


def survey_score_map(survey: models.Survey) -> dict[str, float]:
    return {
        a.question_code: a.value_numeric
        for a in survey.answers
        if a.question_code in SCORE_QUESTION_CODES and a.value_numeric is not None
    }


def question_averages(db: Session, dealership_id: int | None = None, source: str = "direct_call",
                       date_from: dt.date | None = None, date_to: dt.date | None = None) -> dict[str, dict]:
    """Average dealership score per official score-question, with respondent counts."""
    q = select(models.SurveyAnswer, models.Survey).join(models.Survey)
    q = q.where(models.Survey.source == source)
    if dealership_id:
        q = q.where(models.Survey.dealership_id == dealership_id)
    if date_from:
        q = q.where(models.Survey.survey_date >= date_from)
    if date_to:
        q = q.where(models.Survey.survey_date <= date_to)
    rows = db.execute(q).all()

    buckets: dict[str, list[float]] = defaultdict(list)
    for ans, survey in rows:
        if ans.question_code in SCORE_QUESTION_CODES and ans.value_numeric is not None:
            buckets[ans.question_code].append(ans.value_numeric)

    result = {}
    for code in SCORE_QUESTION_CODES:
        vals = buckets.get(code, [])
        result[code] = {
            "label": QUESTION_BY_CODE[code].short_label,
            "avg": round(sum(vals) / len(vals), 2) if vals else None,
            "n": len(vals),
        }
    return result


def overview_metrics(db: Session, surveys: list[models.Survey]) -> dict:
    n = len(surveys)
    csis = [s.csi for s in surveys if s.csi is not None]
    csats = [s.csat for s in surveys if s.csat is not None]
    low_count = sum(1 for s in surveys if s.is_low_score)
    from sqlalchemy import func
    unresolved_count = db.scalar(
        select(func.count(models.InternalFollowUp.id)).where(
            models.InternalFollowUp.followup_result.in_(["حل نشد", "نیازمند اقدام بیشتر", "مشتری پاسخ نداد"])
        )
    ) or 0
    due_count = db.scalar(
        select(func.count(models.InternalFollowUp.id)).where(
            models.InternalFollowUp.needs_followup == True,  # noqa: E712
            models.InternalFollowUp.followup_date.is_not(None),
            models.InternalFollowUp.followup_result.is_(None),
            models.InternalFollowUp.followup_date <= dt.date.today(),
        )
    ) or 0

    return {
        "n_customers": n,
        "csi": round(sum(csis) / len(csis), 2) if csis else None,
        "csat": round(sum(csats) / len(csats), 1) if csats else None,
        "satisfaction_pct": round(100 * sum(1 for s in surveys if (s.csi or 0) >= 7) / n, 1) if n else None,
        "dissatisfaction_pct": round(100 * sum(1 for s in surveys if (s.csi or 10) < 6) / n, 1) if n else None,
        "avg_score": round(sum(csis) / len(csis), 2) if csis else None,
        "unresolved_complaints": unresolved_count,
        "followups_due": due_count,
        "low_score_surveys": low_count,
    }


def trend_over_time(surveys: list[models.Survey]) -> list[dict]:
    monthly: dict[str, list[models.Survey]] = defaultdict(list)
    for s in surveys:
        if s.survey_date:
            monthly[s.survey_date.strftime("%Y-%m")].append(s)
    out = []
    for month in sorted(monthly.keys()):
        group = monthly[month]
        csis = [s.csi for s in group if s.csi is not None]
        csats = [s.csat for s in group if s.csat is not None]
        out.append({
            "month": month,
            "csi": round(sum(csis) / len(csis), 2) if csis else None,
            "csat": round(sum(csats) / len(csats), 1) if csats else None,
            "n": len(group),
        })
    return out


def dissatisfaction_reasons(db: Session) -> list[dict]:
    from sqlalchemy import func
    rows = db.execute(
        select(models.InternalFollowUp.main_reason, func.count(models.InternalFollowUp.id))
        .where(models.InternalFollowUp.main_reason.is_not(None))
        .group_by(models.InternalFollowUp.main_reason)
        .order_by(func.count(models.InternalFollowUp.id).desc())
    ).all()
    total = sum(c for _, c in rows) or 1
    return [{"reason": r, "count": c, "pct": round(100 * c / total, 1)} for r, c in rows]


def lowest_scoring_questions(db: Session, top_n: int = 5, **filters) -> list[dict]:
    avgs = question_averages(db, **filters)
    items = [{"code": code, **data} for code, data in avgs.items() if data["avg"] is not None]
    items.sort(key=lambda x: x["avg"])
    return items[:top_n]


def company_vs_dealership(db: Session, year_month: str, dealership_id: int | None = None) -> dict:
    """Question-by-question + overall gap table for a given company reporting month."""
    company_rows = db.execute(
        select(models.MonthlyCompanyResult).where(models.MonthlyCompanyResult.year_month == year_month)
    ).scalars().all()
    company_overall = next((r for r in company_rows if r.question_code is None), None)
    company_by_q = {r.question_code: r.score for r in company_rows if r.question_code is not None}

    year, month = (int(x) for x in year_month.split("-"))
    from calendar import monthrange
    date_from = dt.date(year, month, 1)
    date_to = dt.date(year, month, monthrange(year, month)[1])

    dealer_avgs = question_averages(db, dealership_id=dealership_id, date_from=date_from, date_to=date_to)
    dealer_surveys = db.execute(
        select(models.Survey).where(
            models.Survey.source == "direct_call",
            models.Survey.survey_date >= date_from,
            models.Survey.survey_date <= date_to,
        )
    ).scalars().all()
    dealer_overview = overview_metrics(db, dealer_surveys)

    rows = []
    if company_overall:
        d_csi = dealer_overview["csi"]
        diff = round((d_csi - company_overall.csi), 2) if (d_csi is not None and company_overall.csi is not None) else None
        rows.append({
            "label": "شاخص کلی (CSI)", "code": None,
            "company": company_overall.csi, "dealership": d_csi, "diff": diff,
        })

    for code in SCORE_QUESTION_CODES:
        company_val = company_by_q.get(code)
        dealer_val = dealer_avgs.get(code, {}).get("avg")
        diff = round(dealer_val - company_val, 2) if (company_val is not None and dealer_val is not None) else None
        rows.append({
            "label": QUESTION_BY_CODE[code].short_label, "code": code,
            "company": company_val, "dealership": dealer_val, "diff": diff,
        })

    scored_rows = [r for r in rows if r["diff"] is not None]
    largest_negative = sorted(scored_rows, key=lambda r: r["diff"])[:5]
    largest_positive = sorted(scored_rows, key=lambda r: -r["diff"])[:5]

    return {
        "year_month": year_month,
        "rows": rows,
        "largest_negative_gaps": largest_negative,
        "largest_positive_gaps": largest_positive,
        "company_csat": company_overall.csat if company_overall else None,
        "dealership_csat": dealer_overview["csat"],
    }


CORRELATION_PAIRS = [
    ("Q4", "Q1", "زمان تعمیر", "رضایت کلی", "تأخیر در تعمیر → رضایت کلی"),
    ("Q8", "Q4", "تأمین قطعه", "رضایت از زمان تعمیر", "تأمین قطعه → رضایت از زمان تعمیر"),
    ("Q13", "Q16", "رفتار پرسنل", "تمایل به معرفی", "رفتار پرسنل → تمایل به معرفی"),
    ("Q17", "Q1", "سهولت فرآیند", "رضایت کلی", "سهولت فرآیند → رضایت کلی"),
]


def correlation_insights(db: Session, min_n: int = 8, **filters) -> list[dict]:
    q = select(models.SurveyAnswer, models.Survey).join(models.Survey).where(models.Survey.source == "direct_call")
    rows = db.execute(q).all()
    by_survey: dict[int, dict] = defaultdict(dict)
    for ans, survey in rows:
        by_survey[survey.id][ans.question_code] = ans.value_numeric

    df = pd.DataFrame.from_dict(by_survey, orient="index")

    insights = []
    for code_x, code_y, label_x, label_y, description in CORRELATION_PAIRS:
        if code_x not in df.columns or code_y not in df.columns:
            continue
        sub = df[[code_x, code_y]].dropna()
        if len(sub) < min_n:
            insights.append({
                "description": description, "n": len(sub), "r": None,
                "note": "داده کافی برای تحلیل همبستگی وجود ندارد (حداقل نمونه لازم است).",
            })
            continue
        r = round(float(sub[code_x].corr(sub[code_y])), 2)
        strength = (
            "قوی" if abs(r) >= 0.6 else "متوسط" if abs(r) >= 0.3 else "ضعیف"
        )
        direction = "مثبت" if r >= 0 else "منفی"
        insights.append({
            "description": description, "n": len(sub), "r": r,
            "note": f"همبستگی {direction} با شدت {strength} (r={r}, n={len(sub)}). این یک رابطه همبستگی است، نه لزوماً علّی.",
        })
    return insights


def action_effectiveness(action: models.CorrectiveAction) -> dict:
    results = sorted(action.results, key=lambda r: r.measured_date)
    latest = results[-1] if results else None
    baseline = action.baseline_value
    target = action.target_value

    improvement = None
    achieved = None
    if latest and baseline is not None:
        improvement = round(latest.measured_value - baseline, 2)
    if latest and target is not None:
        achieved = latest.measured_value >= target

    return {
        "baseline": baseline,
        "target": target,
        "latest": latest.measured_value if latest else None,
        "latest_date": latest.measured_date if latest else None,
        "improvement": improvement,
        "target_achieved": achieved,
        "history": [{"date": r.measured_date, "value": r.measured_value, "note": r.note} for r in results],
    }
