"""
scripts/build_knowledge_base.py
---------------------------------
يُشغَّل مرة واحدة (أو عند استبدال ملفات الكتاب) لبناء قاعدة المعرفة
كاملة: استخراج الكتاب من PDF → تنظيف → تقطيع → حساب متجهات دلالية →
حفظ في PostgreSQL.

الاستخدام:
    python3 scripts/build_knowledge_base.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extract import extract_full_book
from app.chunking import build_all_chunks
from app.embedding import embed_texts
from app import database


def main():
    print("1) استخراج نص الكتاب من ملفات PDF...")
    pages = extract_full_book(data_dir="data")

    pages_path = Path("data") / "book_pages_clean.json"
    import json
    pages_path.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n2) تقطيع النص إلى مقاطع...")
    chunks = build_all_chunks(pages_json_path=str(pages_path))
    print(f"   عدد المقاطع: {len(chunks)}")

    print("\n3) حساب المتجهات الدلالية (قد يستغرق دقائق عند أول تشغيل بسبب تحميل النموذج)...")
    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)
    for chunk, vec in zip(chunks, embeddings):
        chunk["embedding"] = vec

    print("\n4) الحفظ في قاعدة البيانات...")
    database.init_db()
    database.replace_all_chunks(chunks)

    print(f"\nتم بنجاح. عدد المقاطع المفهرسة: {len(chunks)}")


if __name__ == "__main__":
    main()
