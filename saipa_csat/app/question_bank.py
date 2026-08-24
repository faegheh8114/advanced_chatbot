"""
Official survey question bank for Saipa Mashayekh (code 3299).

This is the SINGLE SOURCE OF TRUTH for the official company survey.
Wording, order, scoring scale (0-10) and structure must not be altered.
Internal-only dealership questions live elsewhere (see internal_reasons.py)
and are always kept in a separate data model from these official answers.
"""
from dataclasses import dataclass, field
from typing import Optional


SCORE_0_10 = "score_0_10"
TEXT = "text"
CHOICE = "choice"
YES_NO = "yes_no"
DATETIME = "datetime"


@dataclass(frozen=True)
class Question:
    code: str
    order: int
    text: str
    qtype: str
    interpretation: Optional[str] = None
    options: Optional[tuple] = None
    conditional_on: Optional[str] = None   # code of the question this depends on
    conditional_value: Optional[bool] = None  # required value of that question
    include_in_csi: bool = False
    short_label: str = ""  # short Persian label used in comparison tables/charts


OFFICIAL_QUESTIONS: tuple[Question, ...] = (
    Question(
        code="Q1", order=1, include_in_csi=True,
        short_label="رضایت کلی",
        text="به طور کلی تا چه میزان از خدمات پس از فروش ارائه شده توسط نمایندگی ...... در تاریخ ......... رضایت دارید؟",
        qtype=SCORE_0_10,
        interpretation="0 = کمترین رضایت، 10 = صد درصد رضایت",
    ),
    Question(
        code="Q2", order=2,
        short_label="دلیل مراجعه",
        text="دلیل مراجعه شما به نمایندگی … در این تاریخ چه بوده است؟",
        qtype=CHOICE,
        options=("سرویس دوره‌ای", "ایراد فنی", "صافکاری و نقاشی", "سایر"),
        interpretation="در تاریخ ... برای سرویس، ایراد فنی، صافکاری و نقاشی و یا مورد دیگری به نمایندگی رفتید؟",
    ),
    Question(
        code="Q3", order=3, include_in_csi=True,
        short_label="فرآیند پذیرش",
        text="از فرآیند پذیرش خودرو (زمان و نحوه پذیرش) در نمایندگی چقدر رضایت دارید؟",
        qtype=SCORE_0_10,
        interpretation="مدت زمانی که طول کشید خودرو پذیرش و ایرادات ثبت شود و خودرو از مشتری تحویل گرفته شود.",
    ),
    Question(
        code="Q4", order=4, include_in_csi=True,
        short_label="زمان تعمیر",
        text="از مدت زمان تعمیر خودرو مطابق زمان اعلام شده در زمان پذیرش خودرو چقدر رضایت دارید؟",
        qtype=SCORE_0_10,
        interpretation="سرعت انجام کار نسبت به حجم کار و اینکه طبق زمان اعلام شده در زمان پذیرش، خودرو تحویل داده شد یا خیر.",
    ),
    Question(
        code="Q5", order=5,
        short_label="زمان تحویل",
        text="در این مراجعه خودرو را چه زمانی به شما تحویل دادند؟",
        qtype=DATETIME,
    ),
    Question(
        code="Q6", order=6, include_in_csi=True,
        short_label="کیفیت خدمات",
        text="میزان رضایت شما از کیفیت خدمات ارائه شده از قبیل تعمیرات و سرویس های نمایندگی مطابق خدمات درخواست شده در زمان پذیرش چقدر است؟",
        qtype=SCORE_0_10,
        interpretation="این سوال کیفیت کار انجام شده را می‌سنجد؛ کیفیت قطعه را فقط در صورتی که مشتری صراحتاً به آن اشاره کند مرتبط بدانید.",
    ),
    Question(
        code="Q7", order=7,
        short_label="نیاز به قطعه",
        text="برای تعمیر خودرویتان قطعه مصرفی و غیر مصرفی نیاز بود؟",
        qtype=YES_NO,
    ),
    Question(
        code="Q8", order=8, include_in_csi=True,
        short_label="تأمین قطعه",
        text="از اقدامات و پیگیری نمایندگی در خصوص تأمین قطعات چقدر رضایت دارید؟",
        qtype=SCORE_0_10,
        conditional_on="Q7", conditional_value=True,
        interpretation="فقط برای مشتریانی که واقعاً نیاز به قطعه داشتند محاسبه/تحلیل شود.",
    ),
    Question(
        code="Q9", order=9,
        short_label="پرداخت هزینه",
        text="آیا در این مراجعه هزینه ای بابت خدمات ارائه شده پرداخت نموده اید؟",
        qtype=YES_NO,
    ),
    Question(
        code="Q9b", order=10,
        short_label="نوع هزینه",
        text="نوع هزینه پرداختی:",
        qtype=CHOICE,
        options=("قطعه", "اجرت", "قطعه و اجرت", "سایر"),
        conditional_on="Q9", conditional_value=True,
    ),
    Question(
        code="Q10", order=11, include_in_csi=True,
        short_label="رضایت از هزینه",
        text="از هزینه پرداختی (قطعه و اجرت) متناسب با خدمات انجام شده چقدر رضایت دارید؟",
        qtype=SCORE_0_10,
        conditional_on="Q9", conditional_value=True,
        interpretation="فقط برای مشتریانی که هزینه‌ای پرداخت کرده‌اند محاسبه/تحلیل شود.",
    ),
    Question(
        code="Q11", order=12, include_in_csi=True,
        short_label="امکانات رفاهی",
        text="از امکانات رفاهی ارائه شده در نمایندگی چقدر رضایت دارید؟",
        qtype=SCORE_0_10,
    ),
    Question(
        code="Q12", order=13, include_in_csi=True,
        short_label="کیفیت توضیحات",
        text="از توضیحات ارائه شده در خصوص کارهای انجام شده روی خودرو چقدر رضایت دارید؟",
        qtype=SCORE_0_10,
        interpretation="آیا نمایندگی کارهای انجام‌شده و/یا قطعات تعویضی را توضیح داد؟",
    ),
    Question(
        code="Q13", order=14, include_in_csi=True,
        short_label="رفتار پرسنل",
        text="از نحوه رفتار و برخورد پرسنل تعمیرگاه چقدر رضایت دارید؟",
        qtype=SCORE_0_10,
    ),
    Question(
        code="Q14", order=15, include_in_csi=True,
        short_label="پیگیری پس از ترخیص",
        text="از نحوه پیگیری نمایندگی از طریق تماس، پیامک، اپ و .... در خصوص کیفیت خدمات ارائه شده پس از ترخیص چقدر رضایت دارید؟",
        qtype=SCORE_0_10,
    ),
    Question(
        code="Q15", order=16, include_in_csi=True,
        short_label="سهولت دسترسی",
        text="از سهولت دسترسی به نمایندگی های این شرکت چقدر رضایت دارید؟",
        qtype=SCORE_0_10,
    ),
    Question(
        code="Q16", order=17, include_in_csi=True,
        short_label="تمایل به معرفی",
        text="با توجه به خدماتی که این نمایندگی تاکنون به شما ارائه داده تا چه میزان تمایل دارید این نمایندگی را به دیگران معرفی کنید؟",
        qtype=SCORE_0_10,
    ),
    Question(
        code="Q17", order=18, include_in_csi=True,
        short_label="سهولت فرآیند",
        text="چقدر فرآیند دریافت خدمات پس از فروش برای شما راحت بوده است؟",
        qtype=SCORE_0_10,
    ),
    Question(
        code="Q18", order=19,
        short_label="انتقادات و پیشنهادات",
        text="انتقادات و پیشنهادات:",
        qtype=TEXT,
    ),
)

QUESTION_BY_CODE = {q.code: q for q in OFFICIAL_QUESTIONS}
CSI_QUESTION_CODES = tuple(q.code for q in OFFICIAL_QUESTIONS if q.include_in_csi)
SCORE_QUESTION_CODES = tuple(q.code for q in OFFICIAL_QUESTIONS if q.qtype == SCORE_0_10)

# Categories for internal "reason for dissatisfaction" follow-up (triggered on low scores).
DISSATISFACTION_REASONS = (
    "پذیرش", "تأخیر در تعمیر", "کیفیت خدمات", "تأمین قطعه", "هزینه",
    "امکانات رفاهی", "توضیحات ناکافی", "رفتار پرسنل", "پیگیری پس از ترخیص",
    "دسترسی", "سختی فرآیند", "سایر",
)

CORRECTIVE_ACTION_TYPES = (
    "تماس مدیر", "تماس مسئول مربوطه", "بررسی خودرو", "تأمین قطعه", "اصلاح فرآیند",
    "اصلاح هزینه", "آموزش پرسنل", "توضیح مجدد به مشتری", "پیگیری مجدد",
    "ارجاع به واحد مربوطه", "سایر",
)

FOLLOWUP_RESULT_STATUSES = (
    "حل شد", "تا حدی حل شد", "حل نشد", "مشتری پاسخ نداد", "نیازمند اقدام بیشتر",
)

LOW_SCORE_THRESHOLD = 6  # Q1 (or any core question) below this triggers internal follow-up

# Maps a dissatisfaction reason to the operational owner responsible for corrective action.
REASON_OWNER_MAP = {
    "پذیرش": "واحد پذیرش",
    "تأخیر در تعمیر": "واحد فنی / برنامه‌ریزی تعمیرگاه",
    "کیفیت خدمات": "واحد فنی",
    "تأمین قطعه": "واحد قطعات (انبار)",
    "هزینه": "واحد مالی / صندوق",
    "امکانات رفاهی": "واحد خدمات مشتریان",
    "توضیحات ناکافی": "واحد پذیرش / مشاور خدمات",
    "رفتار پرسنل": "مدیریت منابع انسانی / سرپرست تعمیرگاه",
    "پیگیری پس از ترخیص": "واحد ارتباط با مشتری (CRM)",
    "دسترسی": "مدیریت نمایندگی",
    "سختی فرآیند": "مدیریت فرآیندها",
    "سایر": "مدیریت نمایندگی",
}

# Maps each score question relevant to the comparison/root-cause engine to the
# dissatisfaction reason it most directly reflects (used to link low question
# scores to actionable categories automatically).
QUESTION_TO_REASON = {
    "Q3": "پذیرش",
    "Q4": "تأخیر در تعمیر",
    "Q6": "کیفیت خدمات",
    "Q8": "تأمین قطعه",
    "Q10": "هزینه",
    "Q11": "امکانات رفاهی",
    "Q12": "توضیحات ناکافی",
    "Q13": "رفتار پرسنل",
    "Q14": "پیگیری پس از ترخیص",
    "Q15": "دسترسی",
    "Q17": "سختی فرآیند",
}
