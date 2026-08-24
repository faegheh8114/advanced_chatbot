"""Excel import for the company's official monthly survey export, and
generic export helpers. Import never silently modifies data: every row is
validated and previewed before anything is written to the database, and
imported surveys are tagged source="company_import" so they never mix with
direct-call data used elsewhere in the app.
"""
import io
import uuid
import datetime as dt
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select

from . import models
from .question_bank import OFFICIAL_QUESTIONS, QUESTION_BY_CODE, SCORE_0_10, YES_NO, TEXT, CHOICE, DATETIME
from .analytics import compute_csi_csat

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

REQUIRED_FIELDS = ["customer_name", "phone", "survey_date"]
MAPPABLE_FIELDS = REQUIRED_FIELDS + [q.code for q in OFFICIAL_QUESTIONS]


def save_upload(content: bytes) -> str:
    import_id = uuid.uuid4().hex
    (UPLOAD_DIR / f"{import_id}.xlsx").write_bytes(content)
    return import_id


def load_dataframe(import_id: str) -> pd.DataFrame:
    path = UPLOAD_DIR / f"{import_id}.xlsx"
    return pd.read_excel(path, dtype=str)


def suggest_mapping(df: pd.DataFrame) -> dict[str, str]:
    """Best-effort auto mapping of excel columns -> our fields, by exact/loose match.
    Never applied silently — always shown to the user for confirmation."""
    mapping = {}
    lookup = {
        "customer_name": ["نام", "نام مشتری", "نام و نام خانوادگی", "customer", "name"],
        "phone": ["تلفن", "شماره تماس", "موبایل", "phone"],
        "survey_date": ["تاریخ", "تاریخ مراجعه", "date"],
    }
    for col in df.columns:
        col_norm = str(col).strip()
        if col_norm in QUESTION_BY_CODE:
            mapping[col] = col_norm
            continue
        matched = None
        for code, q in QUESTION_BY_CODE.items():
            if col_norm == q.short_label or col_norm == q.text:
                matched = code
                break
        if matched:
            mapping[col] = matched
            continue
        for field, keywords in lookup.items():
            if any(k in col_norm for k in keywords):
                matched = field
                break
        mapping[col] = matched or ""
    return mapping


def validate(df: pd.DataFrame, mapping: dict[str, str]) -> dict:
    errors: list[str] = []
    row_issues: list[dict] = []

    mapped_targets = [v for v in mapping.values() if v]
    for req in REQUIRED_FIELDS:
        if req not in mapped_targets:
            errors.append(f"ستون الزامی نگاشت نشده است: {req}")

    seen_keys = set()
    for idx, row in df.iterrows():
        issues = []
        rec = {target: row[col] for col, target in mapping.items() if target}

        date_val = None
        if "survey_date" in rec:
            try:
                date_val = pd.to_datetime(rec["survey_date"]).date()
            except Exception:
                issues.append("تاریخ نامعتبر")

        phone = str(rec.get("phone", "")).strip()
        if not phone or phone == "nan":
            issues.append("شماره تماس خالی است")

        key = (phone, str(date_val))
        if key in seen_keys and phone:
            issues.append("رکورد تکراری (تلفن و تاریخ مشابه)")
        seen_keys.add(key)

        for code in [c for c in mapped_targets if c in QUESTION_BY_CODE]:
            q = QUESTION_BY_CODE[code]
            val = rec.get(code)
            if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() in ("", "nan"):
                continue
            if q.qtype == SCORE_0_10:
                try:
                    num = float(val)
                    if not (0 <= num <= 10):
                        issues.append(f"مقدار خارج از بازه ۰ تا ۱۰ برای {code}: {val}")
                except ValueError:
                    issues.append(f"مقدار عددی نامعتبر برای {code}: {val}")
            elif q.qtype == YES_NO:
                if str(val).strip().lower() not in ("بله", "خیر", "yes", "no", "1", "0", "true", "false"):
                    issues.append(f"مقدار بله/خیر نامعتبر برای {code}: {val}")

        if issues:
            row_issues.append({"row": int(idx) + 2, "issues": issues})

    return {
        "n_rows": len(df),
        "n_invalid_rows": len(row_issues),
        "n_valid_rows": len(df) - len(row_issues),
        "errors": errors,
        "row_issues": row_issues,          # full list — used to decide which rows to skip on commit
        "row_issues_preview": row_issues[:200],  # capped list for on-screen display only
        "can_commit": not errors,
    }


def _parse_bool(val) -> bool | None:
    s = str(val).strip().lower()
    if s in ("بله", "yes", "1", "true"):
        return True
    if s in ("خیر", "no", "0", "false"):
        return False
    return None


def commit_import(db: Session, df: pd.DataFrame, mapping: dict[str, str], dealership_id: int, user_id: int) -> dict:
    """Only rows that pass validate() unchanged are written — invalid values
    (e.g. an out-of-range score) are never silently coerced, the whole row is
    skipped instead so the operator can see exactly what wasn't imported."""
    validation = validate(df, mapping)
    invalid_rows = {ri["row"] for ri in validation["row_issues"]}

    created, skipped = 0, 0
    for idx, row in df.iterrows():
        if (idx + 2) in invalid_rows:
            skipped += 1
            continue
        rec = {target: row[col] for col, target in mapping.items() if target}
        phone = str(rec.get("phone", "")).strip()
        name = str(rec.get("customer_name", "")).strip() or "نامشخص"
        if not phone or phone == "nan":
            skipped += 1
            continue
        try:
            survey_date = pd.to_datetime(rec.get("survey_date")).date()
        except Exception:
            skipped += 1
            continue

        customer = db.execute(select(models.Customer).where(models.Customer.phone == phone)).scalars().first()
        if not customer:
            customer = models.Customer(full_name=name, phone=phone)
            db.add(customer)
            db.flush()

        existing = db.execute(
            select(models.Survey).where(
                models.Survey.customer_id == customer.id,
                models.Survey.survey_date == survey_date,
                models.Survey.source == "company_import",
            )
        ).scalars().first()
        if existing:
            skipped += 1
            continue

        survey = models.Survey(
            customer_id=customer.id, dealership_id=dealership_id, survey_date=survey_date,
            source="company_import", created_by=user_id, updated_by=user_id,
        )
        db.add(survey)
        db.flush()

        score_values = {}
        for code, q in QUESTION_BY_CODE.items():
            if code not in rec:
                continue
            val = rec[code]
            if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() in ("", "nan"):
                continue
            answer = models.SurveyAnswer(survey_id=survey.id, question_code=code)
            if q.qtype == SCORE_0_10:
                try:
                    num = max(0.0, min(10.0, float(val)))
                except ValueError:
                    continue
                answer.value_numeric = num
                score_values[code] = num
            elif q.qtype == YES_NO:
                answer.value_bool = _parse_bool(val)
            elif q.qtype == CHOICE or q.qtype == TEXT:
                answer.value_text = str(val)
            elif q.qtype == DATETIME:
                try:
                    answer.value_datetime = pd.to_datetime(val).to_pydatetime()
                except Exception:
                    continue
            db.add(answer)

        csi, csat = compute_csi_csat(score_values)
        survey.csi = csi
        survey.csat = csat
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped}


# ---------------- Export helpers ----------------

def dataframe_to_xlsx_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return buf.getvalue()


def surveys_dataframe(db: Session, source: str | None = None) -> pd.DataFrame:
    q = select(models.Survey)
    if source:
        q = q.where(models.Survey.source == source)
    surveys = db.execute(q).scalars().all()
    rows = []
    for s in surveys:
        row = {
            "customer": s.customer.full_name, "phone": s.customer.phone,
            "survey_date": s.survey_date, "source": s.source, "csi": s.csi, "csat": s.csat,
        }
        for a in s.answers:
            if a.value_numeric is not None:
                row[a.question_code] = a.value_numeric
            elif a.value_bool is not None:
                row[a.question_code] = "بله" if a.value_bool else "خیر"
            elif a.value_text:
                row[a.question_code] = a.value_text
        rows.append(row)
    return pd.DataFrame(rows)


def followups_dataframe(db: Session) -> pd.DataFrame:
    rows = db.execute(select(models.InternalFollowUp)).scalars().all()
    return pd.DataFrame([{
        "مشتری": f.survey.customer.full_name if f.survey else "",
        "علت اصلی": f.main_reason, "قابل اقدام": f.is_actionable, "اقدام": f.action_taken_type,
        "نیاز به پیگیری": f.needs_followup, "تاریخ پیگیری": f.followup_date,
        "نتیجه": f.followup_result, "نمره پس از پیگیری": f.followup_score,
    } for f in rows])


def actions_dataframe(db: Session) -> pd.DataFrame:
    rows = db.execute(select(models.CorrectiveAction)).scalars().all()
    return pd.DataFrame([{
        "عنوان": a.title, "مسئله": a.problem, "علت ریشه‌ای": a.root_cause, "اقدام": a.action,
        "مسئول": a.owner, "مهلت": a.deadline, "KPI": a.kpi_name, "پایه": a.baseline_value,
        "هدف": a.target_value, "وضعیت": a.status,
    } for a in rows])
