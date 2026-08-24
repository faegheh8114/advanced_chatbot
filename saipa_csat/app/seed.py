"""Idempotent startup seed: dealership, official question bank mirror, demo
users, and enough sample data so the dashboard/analytics are not empty on
first run. Safe to call on every startup — it only inserts what's missing."""
import datetime as dt
import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .auth import hash_password
from .analytics import compute_csi_csat
from .question_bank import OFFICIAL_QUESTIONS, CSI_QUESTION_CODES, DISSATISFACTION_REASONS, \
    CORRECTIVE_ACTION_TYPES, FOLLOWUP_RESULT_STATUSES, QUESTION_TO_REASON

DEMO_CUSTOMER_NAMES = [
    "علی محمدی", "زهرا احمدی", "حسین رضایی", "فاطمه کریمی", "محمد حسینی",
    "مریم صادقی", "رضا موسوی", "سارا نوری", "امیر جعفری", "نگار قاسمی",
    "کاظم شریفی", "لیلا رستمی", "حمید طاهری", "الهام یزدانی", "بهروز فرهادی",
    "مینا اسدی", "پیمان کاظمی", "شیرین محمودی", "داوود ملکی", "آزاده رحیمی",
    "فرهاد امینی", "نسرین قربانی", "یوسف صالحی", "پریسا نجفی", "کامران دهقانی",
]
VEHICLE_MODELS = ["تیبا", "ساینا", "کوئیک", "شاهین", "پراید ۱۳۱"]


def _rand_score(mean: float, spread: float = 1.5) -> float:
    val = random.gauss(mean, spread)
    return round(max(0, min(10, val)) * 2) / 2  # nearest 0.5


def run_seed(db: Session) -> None:
    dealership = db.execute(select(models.Dealership)).scalars().first()
    if not dealership:
        dealership = models.Dealership(name="سایپا مشایخ کد 3299", code="3299")
        db.add(dealership)
        db.flush()

    for q in OFFICIAL_QUESTIONS:
        if not db.get(models.OfficialQuestion, q.code):
            db.add(models.OfficialQuestion(
                code=q.code, order=q.order, text=q.text, qtype=q.qtype, short_label=q.short_label,
            ))

    admin = db.execute(select(models.User).where(models.User.username == "admin")).scalars().first()
    if not admin:
        db.add(models.User(
            username="admin", full_name="مدیر نمایندگی", role="admin",
            password_hash=hash_password("admin123"),
        ))
    staff = db.execute(select(models.User).where(models.User.username == "staff1")).scalars().first()
    if not staff:
        db.add(models.User(
            username="staff1", full_name="کارشناس تماس", role="staff",
            password_hash=hash_password("staff123"),
        ))
    db.commit()

    existing_customers = db.execute(select(models.Customer)).scalars().first()
    if existing_customers:
        return  # demo survey/company data already seeded

    staff_user = db.execute(select(models.User).where(models.User.username == "staff1")).scalars().first()
    admin_user = db.execute(select(models.User).where(models.User.username == "admin")).scalars().first()
    dealership = db.execute(select(models.Dealership)).scalars().first()

    random.seed(42)
    today = dt.date.today()

    for i, name in enumerate(DEMO_CUSTOMER_NAMES):
        customer = models.Customer(
            full_name=name,
            phone=f"0912{1000000 + i * 37:07d}",
            vehicle_model=random.choice(VEHICLE_MODELS),
            gender=random.choice(["مرد", "زن"]),
            age=random.randint(22, 60),
            education=random.choice(["دیپلم", "کاردانی", "کارشناسی", "کارشناسی ارشد و بالاتر"]),
            job=random.choice(["کارمند", "آزاد", "خانه‌دار", "بازنشسته"]),
        )
        db.add(customer)
        db.flush()

        n_visits = random.choice([1, 1, 2])
        for v in range(n_visits):
            survey_date = today - dt.timedelta(days=random.randint(1, 110))
            is_bad = random.random() < 0.28
            mean = 4.6 if is_bad else 8.1

            survey = models.Survey(
                customer_id=customer.id, dealership_id=dealership.id, staff_id=staff_user.id,
                survey_date=survey_date, source="direct_call",
                created_by=staff_user.id, updated_by=staff_user.id,
            )
            db.add(survey)
            db.flush()

            score_values = {}
            for code in CSI_QUESTION_CODES:
                if code in ("Q8", "Q10"):
                    continue  # conditional questions, added below only when applicable
                val = _rand_score(mean)
                score_values[code] = val
                db.add(models.SurveyAnswer(survey_id=survey.id, question_code=code, value_numeric=val))

            needed_parts = random.random() < 0.6
            db.add(models.SurveyAnswer(survey_id=survey.id, question_code="Q7", value_bool=needed_parts))
            if needed_parts:
                parts_score = _rand_score(mean - 0.5 if is_bad else mean)
                score_values["Q8"] = parts_score
                db.add(models.SurveyAnswer(survey_id=survey.id, question_code="Q8", value_numeric=parts_score))

            paid = random.random() < 0.7
            db.add(models.SurveyAnswer(survey_id=survey.id, question_code="Q9", value_bool=paid))
            if paid:
                db.add(models.SurveyAnswer(survey_id=survey.id, question_code="Q9b", value_text=random.choice(["قطعه", "اجرت", "قطعه و اجرت"])))
                cost_score = _rand_score(mean)
                score_values["Q10"] = cost_score
                db.add(models.SurveyAnswer(survey_id=survey.id, question_code="Q10", value_numeric=cost_score))

            db.add(models.SurveyAnswer(
                survey_id=survey.id, question_code="Q2",
                value_text=random.choice(["سرویس دوره‌ای", "ایراد فنی", "صافکاری و نقاشی"]),
            ))
            db.add(models.SurveyAnswer(
                survey_id=survey.id, question_code="Q5",
                value_datetime=dt.datetime.combine(survey_date, dt.time(hour=random.randint(13, 18))),
            ))
            if is_bad and random.random() < 0.5:
                db.add(models.SurveyAnswer(
                    survey_id=survey.id, question_code="Q18",
                    value_text=random.choice([
                        "زمان تحویل خودرو بیشتر از حد اعلام‌شده طول کشید.",
                        "قطعه مورد نیاز با تأخیر تأمین شد.",
                        "توضیحات کافی درباره کارهای انجام‌شده داده نشد.",
                    ]),
                ))

            csi, csat = compute_csi_csat(score_values)
            survey.csi = csi
            survey.csat = csat
            survey.is_low_score = any(val < 6 for val in score_values.values())

            if survey.is_low_score:
                worst_code = min(score_values, key=score_values.get)
                reason = QUESTION_TO_REASON.get(worst_code, "سایر")
                result_status = random.choice(FOLLOWUP_RESULT_STATUSES)
                fu_date = survey_date + dt.timedelta(days=random.randint(1, 5))
                db.add(models.InternalFollowUp(
                    survey_id=survey.id,
                    main_reason=reason,
                    customer_explanation="مشتری از " + reason + " ابراز نارضایتی کرد.",
                    is_actionable=True,
                    action_taken_type=random.choice(CORRECTIVE_ACTION_TYPES),
                    action_description="پیگیری توسط کارشناس تماس انجام شد.",
                    needs_followup=True,
                    followup_date=fu_date,
                    followup_result=result_status if fu_date < today else None,
                    followup_score=_rand_score(7.0) if result_status == "حل شد" and fu_date < today else None,
                    created_by=staff_user.id, updated_by=staff_user.id,
                ))

    # Company official monthly results for the last 3 months
    for m_back in range(3):
        month_date = today.replace(day=1)
        for _ in range(m_back):
            month_date = (month_date - dt.timedelta(days=1)).replace(day=1)
        ym = month_date.strftime("%Y-%m")
        db.add(models.MonthlyCompanyResult(year_month=ym, question_code=None, csi=8.1, csat=81.0, created_by=admin_user.id))
        company_question_scores = {
            "Q1": 8.1, "Q3": 8.3, "Q4": 7.8, "Q6": 8.0, "Q11": 7.9, "Q12": 8.0,
            "Q13": 8.5, "Q14": 7.6, "Q15": 8.2, "Q16": 8.4, "Q17": 8.0,
        }
        for code, score in company_question_scores.items():
            db.add(models.MonthlyCompanyResult(year_month=ym, question_code=code, score=score, created_by=admin_user.id))

    db.commit()

    # One example corrective action with a measurement history
    lowest_survey = db.execute(select(models.Survey).where(models.Survey.is_low_score.is_(True))).scalars().first()
    if lowest_survey:
        action = models.CorrectiveAction(
            title="بهبود رضایت از زمان تعمیر",
            problem="میانگین رضایت از زمان تعمیر پایین‌تر از سطح مطلوب است.",
            evidence="بخش قابل توجهی از تماس‌های نارضایتی به تأخیر در تعمیر مرتبط بوده‌اند.",
            root_cause="تأخیر در تعمیر",
            action="بازنگری زمان‌بندی پذیرش و اولویت‌بندی کارهای دارای زمان تحویل اعلام‌شده",
            owner="واحد فنی / برنامه‌ریزی تعمیرگاه",
            deadline=today + dt.timedelta(days=10),
            related_question_code="Q4", related_reason="تأخیر در تعمیر",
            kpi_name="میانگین امتیاز رضایت از زمان تعمیر (Q4)",
            baseline_value=6.2, target_value=7.8, status="در حال اجرا",
            created_by=admin_user.id, updated_by=admin_user.id,
        )
        db.add(action)
        db.flush()
        db.add(models.ActionFollowUp(action_id=action.id, measured_date=today - dt.timedelta(days=20), measured_value=6.2, note="مقدار پایه", created_by=admin_user.id))
        db.add(models.ActionFollowUp(action_id=action.id, measured_date=today - dt.timedelta(days=5), measured_value=7.1, note="اندازه‌گیری میان‌دوره‌ای", created_by=admin_user.id))
        db.commit()
