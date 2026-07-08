"""app/config.py — كل الإعدادات تُقرأ من متغيرات البيئة، بدون أي قيمة افتراضية لبيانات حساسة."""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"متغير البيئة المطلوب غير موجود: {name}")
    return value


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = _require("DEEPSEEK_API_KEY")
DATABASE_URL = _require("DATABASE_URL")

# لا قيمة افتراضية لمعرّف الأدمن — درس مستفاد من مراجعة بوت المعهد
# (كان معرّف الأدمن هناك مكتوباً كقيمة افتراضية في مستودع عام).
ADMIN_ID = int(_require("ADMIN_ID"))

# اسم موديل DeepSeek قابل للتغيير عبر البيئة دون تعديل الكود — يتفادى
# مشكلة كانت موجودة في بوت المعهد (اسم موديل مكتوب مباشرة في الكود
# سيُلغى قريباً من DeepSeek).
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

BOOK_TITLE = "دروس منهجية في شرح عقائد الإمامية"
BOOK_AUTHOR = "الشيخ حسين الأسدي"

NO_ANSWER_MESSAGE = (
    "عذراً، لم أجد في الكتاب المعتمد إجابة واضحة عن هذا السؤال."
)
