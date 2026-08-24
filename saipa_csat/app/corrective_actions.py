"""Data-grounded corrective-action suggestion generator.

Every suggestion is built from real computed numbers (question averages,
dissatisfaction-reason frequencies) — never a generic canned statement.
Management reviews a suggestion and explicitly turns it into a tracked
CorrectiveAction; nothing is auto-created.
"""
import datetime as dt

from sqlalchemy.orm import Session

from . import analytics
from .question_bank import QUESTION_TO_REASON, REASON_OWNER_MAP

ACTION_TEMPLATES = {
    "پذیرش": "بازبینی فرآیند پذیرش خودرو و کاهش زمان انتظار مشتری در زمان پذیرش",
    "تأخیر در تعمیر": "بررسی علل تأخیر در تعمیر و اطمینان از تطابق زمان تحویل با زمان اعلام‌شده در پذیرش",
    "کیفیت خدمات": "استقرار بازرسی کیفی مجدد خودروهای تعمیر شده پیش از ترخیص توسط سرپرست فنی",
    "تأمین قطعه": "بررسی و تأیید موجودی قطعه پیش از پذیرش خودروهایی که نیاز به قطعه مشخص دارند",
    "هزینه": "شفاف‌سازی برآورد هزینه در زمان پذیرش و تطبیق دقیق آن با صورت‌حساب نهایی",
    "امکانات رفاهی": "بهبود امکانات رفاهی سالن انتظار مشتریان",
    "توضیحات ناکافی": "الزام مشاوران خدمات به ارائه توضیح کامل کارهای انجام‌شده و قطعات تعویضی به مشتری",
    "رفتار پرسنل": "برگزاری دوره آموزش رفتار حرفه‌ای با مشتری برای پرسنل تعمیرگاه",
    "پیگیری پس از ترخیص": "استقرار فرآیند تماس/پیامک پیگیری منظم با مشتری پس از ترخیص خودرو",
    "دسترسی": "بررسی راهکارهای افزایش سهولت دسترسی مشتریان به نمایندگی",
    "سختی فرآیند": "ساده‌سازی مراحل دریافت خدمات پس از فروش",
    "سایر": "بررسی موردی هر مورد و تعیین اقدام متناسب با شرح مشتری",
}


def generate_suggestions(db: Session, top_n: int = 3) -> list[dict]:
    lowest = analytics.lowest_scoring_questions(db, top_n=top_n)
    reasons = {r["reason"]: r for r in analytics.dissatisfaction_reasons(db)}

    suggestions = []
    for item in lowest:
        code = item["code"]
        reason = QUESTION_TO_REASON.get(code, "سایر")
        reason_stat = reasons.get(reason)

        evidence_parts = [
            f"میانگین رضایت مشتریان از «{item['label']}» برابر {item['avg']} از ۱۰ است "
            f"(بر اساس {item['n']} پاسخ مستقیم تماس تلفنی)."
        ]
        if reason_stat:
            evidence_parts.append(
                f"{reason_stat['pct']}% از موارد نارضایتی ثبت‌شده در پیگیری‌های داخلی، علت اصلی «{reason}» را دلیل نارضایتی ذکر کرده‌اند "
                f"({reason_stat['count']} مورد)."
            )

        target = round(min(10.0, item["avg"] + 1.5), 1) if item["avg"] is not None else None

        suggestions.append({
            "title": f"بهبود «{item['label']}»",
            "problem": f"شاخص «{item['label']}» با میانگین {item['avg']} از ۱۰ یکی از پایین‌ترین امتیازات پرسش‌نامه رسمی است.",
            "evidence": " ".join(evidence_parts),
            "root_cause": reason,
            "action": ACTION_TEMPLATES.get(reason, ACTION_TEMPLATES["سایر"]),
            "owner": REASON_OWNER_MAP.get(reason, "مدیریت نمایندگی"),
            "deadline": (dt.date.today() + dt.timedelta(days=7)).isoformat(),
            "related_question_code": code,
            "related_reason": reason,
            "kpi_name": f"میانگین امتیاز «{item['label']}» ({code})",
            "baseline_value": item["avg"],
            "target_value": target,
        })
    return suggestions
