"""
run.py
-------
نقطة التشغيل: بناء تطبيق تيليجرام، تحميل مقاطع الكتاب من قاعدة
البيانات مرة واحدة عند الإقلاع، وربط المعالجات. لا منطق أعمال هنا —
هذا الفصل هو أحد الإصلاحات الموصى بها بعد مراجعة بوت المعهد.
"""

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.config import TELEGRAM_BOT_TOKEN
from app import database
from app.handlers import start_command, id_command, stats_command, handle_message, CHUNKS_KEY
from app.logger import get_logger

logger = get_logger(__name__)


def main():
    database.init_db()

    chunks = database.load_all_chunks()
    logger.info("تحميل %d مقطع من قاعدة المعرفة", len(chunks))
    if not chunks:
        logger.warning(
            "قاعدة المعرفة فارغة — شغّل scripts/build_knowledge_base.py أولاً "
            "لاستخراج الكتاب وفهرسته قبل تشغيل البوت."
        )

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.bot_data[CHUNKS_KEY] = chunks

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("البوت يعمل الآن...")
    application.run_polling()


if __name__ == "__main__":
    main()
