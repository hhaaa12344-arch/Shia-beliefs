"""
app/handlers.py
------------------
معالجات تيليجرام. مفصولة عن نقطة التشغيل (run.py) تماشياً مع بند
البنية المعيارية — وهذا الفصل تحديداً كان أحد النواقص المكتشفة في
مراجعة بوت المعهد (حيث كانت المعالجات وتشغيل التطبيق مختلطين في ملف
واحد، وملف handlers.py كان موجوداً لكن فارغاً).
"""

from telegram import Update
from telegram.ext import ContextTypes

from app.config import ADMIN_ID
from app.ai import answer_question
from app import database
from app.logger import get_logger

logger = get_logger(__name__)

# تُحمَّل مرة واحدة عند إقلاع التطبيق (انظر run.py) وتُمرَّر عبر
# context.bot_data بدل متغير عام، لتفادي مشاكل الحالة المشتركة.
CHUNKS_KEY = "book_chunks"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.register_user(user.id, user.username)
    await update.message.reply_text(
        "السلام عليكم، أنا مساعد للإجابة عن الأسئلة العقائدية اعتماداً على "
        "كتاب «دروس منهجية في شرح عقائد الإمامية» للشيخ حسين الأسدي. "
        "اسألني عن أي موضوع عقائدي وسأجيبك مع ذكر مصدر الإجابة من الكتاب."
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"معرّفك: {update.effective_user.id}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    stats = database.get_stats()
    await update.message.reply_text(
        f"👥 المستخدمون: {stats['total_users']}\n"
        f"💬 إجمالي الأسئلة: {stats['total_messages']}\n"
        f"📅 أسئلة اليوم: {stats['today_messages']}\n"
        f"📚 مقاطع الكتاب المفهرسة: {len(context.bot_data.get(CHUNKS_KEY, []))}"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    question = (update.message.text or "").strip()
    if not question:
        return

    database.register_user(user.id, user.username)

    chunks = context.bot_data.get(CHUNKS_KEY, [])

    waiting = await update.message.reply_text("⏳ جارٍ البحث في الكتاب...")

    try:
        answer, path = answer_question(user.id, question, chunks)
        logger.info("user=%s path=%s question=%r", user.id, path, question[:80])
        database.log_message(user.id, question, path)
        await waiting.edit_text(answer)
    except Exception:
        logger.exception("فشل غير متوقع أثناء معالجة السؤال user=%s", user.id)
        await waiting.edit_text("عذراً، حدث خطأ غير متوقع. حاول مرة أخرى بعد قليل.")
