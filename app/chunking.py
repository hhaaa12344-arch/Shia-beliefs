"""
app/chunking.py
-----------------
تحويل صفحات الكتاب النظيفة (من extract.py) إلى مقاطع (chunks) متماسكة
معنوياً، كل مقطع يحمل معه بيانات الاستشهاد الكاملة: اسم الكتاب، اسم
المؤلف، رقم الجزء، رقم الصفحة (أو مدى الصفحات إن امتد المقطع لأكثر
من صفحة).

استراتيجية التقطيع:
- تُدمج الصفحات المتتالية ضمن نفس الجزء في نص متصل واحد أولاً، حتى لا
  تُقطَّع فقرة في منتصفها لمجرد أنها تجاوزت حافة صفحة PDF.
- يُقسَّم النص المتصل إلى مقاطع عند حدود الفقرات (سطر فارغ) بشكل
  أساسي، مع حد أقصى لطول المقطع (بالأحرف) لتفادي مقاطع ضخمة تُثقل
  سياق DeepSeek لاحقاً.
- كل مقطع يُسجَّل معه أول وآخر رقم صفحة يغطيه، لبناء استشهاد دقيق
  حتى لو امتد المقطع بين صفحتين.
"""

import json
from pathlib import Path

BOOK_TITLE = "دروس منهجية في شرح عقائد الإمامية"
BOOK_AUTHOR = "الشيخ حسين الأسدي"

MAX_CHUNK_CHARS = 1200
MIN_CHUNK_CHARS = 200


def _merge_part_pages(pages: list[dict]) -> str:
    """
    يدمج صفحات جزء واحد في نص متصل، مع إدراج علامة غير مرئية بعد كل
    صفحة تحمل رقمها، لاستخدامها لاحقاً في تحديد مدى صفحات كل مقطع.
    الشكل: <<PAGE:23>> قبل نص كل صفحة.
    """
    parts = []
    for p in pages:
        page_no = p["page_number"] if p["page_number"] is not None else p["pdf_page_index"]
        parts.append(f"<<PAGE:{page_no}>>\n{p['text']}")
    return "\n\n".join(parts)


def _split_into_paragraphs(merged_text: str) -> list[tuple[int, str]]:
    """
    يُرجع قائمة (رقم_الصفحة, نص_الفقرة) بعد فصل النص المدمج عند حدود
    الصفحات والفقرات (سطر فارغ).
    """
    result = []
    current_page = None
    for block in merged_text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("<<PAGE:"):
            end = block.find(">>")
            current_page = int(block[7:end])
            block = block[end + 2:].strip()
            if not block:
                continue
        if block:
            result.append((current_page, block))
    return result


def build_chunks_for_part(pages: list[dict]) -> list[dict]:
    """يبني مقاطع جزء واحد من الكتاب."""
    merged = _merge_part_pages(pages)
    paragraphs = _split_into_paragraphs(merged)

    chunks = []
    buffer_text = []
    buffer_pages = []

    def flush():
        if not buffer_text:
            return
        text = "\n".join(buffer_text).strip()
        if len(text) < MIN_CHUNK_CHARS and chunks:
            # مقطع صغير جداً: يُدمج مع المقطع السابق بدل أن يبقى منعزلاً
            prev = chunks[-1]
            prev["text"] = prev["text"] + "\n" + text
            prev["page_end"] = buffer_pages[-1]
        else:
            chunks.append({
                "part": pages[0]["part"],
                "page_start": buffer_pages[0],
                "page_end": buffer_pages[-1],
                "text": text,
            })
        buffer_text.clear()
        buffer_pages.clear()

    for page_no, paragraph in paragraphs:
        candidate_len = sum(len(t) for t in buffer_text) + len(paragraph)
        if candidate_len > MAX_CHUNK_CHARS and buffer_text:
            flush()
        buffer_text.append(paragraph)
        buffer_pages.append(page_no)

    flush()
    return chunks


def build_all_chunks(pages_json_path: str = "data/book_pages_clean.json") -> list[dict]:
    all_pages = json.loads(Path(pages_json_path).read_text(encoding="utf-8"))
    content_pages = [p for p in all_pages if not p.get("is_index_page")]

    by_part: dict[int, list[dict]] = {}
    for p in content_pages:
        by_part.setdefault(p["part"], []).append(p)

    all_chunks = []
    chunk_id = 1
    for part in sorted(by_part):
        part_pages = sorted(by_part[part], key=lambda p: p["pdf_page_index"])
        part_chunks = build_chunks_for_part(part_pages)
        for c in part_chunks:
            c["chunk_id"] = chunk_id
            c["book_title"] = BOOK_TITLE
            c["book_author"] = BOOK_AUTHOR
            chunk_id += 1
        all_chunks.extend(part_chunks)

    return all_chunks


def citation_label(chunk: dict) -> str:
    """يبني نص الاستشهاد القياسي لمقطع معيّن."""
    title = chunk.get("book_title", BOOK_TITLE)
    author = chunk.get("book_author", BOOK_AUTHOR)
    if chunk["page_start"] == chunk["page_end"]:
        page_part = f"صفحة {chunk['page_start']}"
    else:
        page_part = f"صفحة {chunk['page_start']}-{chunk['page_end']}"
    return f"{title} - {author}، الجزء {chunk['part']}، {page_part}"


if __name__ == "__main__":
    chunks = build_all_chunks()
    lengths = [len(c["text"]) for c in chunks]

    print(f"إجمالي المقاطع: {len(chunks)}")
    print(f"متوسط طول المقطع: {sum(lengths)//len(lengths)} حرف")
    print(f"أطول مقطع: {max(lengths)} | أقصر مقطع: {min(lengths)}")

    print("\nمثال على مقطع واستشهاده:")
    sample = chunks[50]
    print("الاستشهاد:", citation_label(sample))
    print("النص:", sample["text"][:200], "...")

    out_path = Path("data") / "book_chunks.json"
    out_path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nتم الحفظ في: {out_path}")
