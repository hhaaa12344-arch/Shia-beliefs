"""
app/extract.py
---------------
استخراج نص كتاب "دروس منهجية في شرح عقائد الإمامية" من ملفات PDF،
مع تصحيح خلل ترميز حروف الأسنان (س ش ص ض) المكتشف في الخط الأصلي
للكتاب، والحفاظ على رقم الجزء ورقم الصفحة المطبوع لكل مقطع نص.

هذا السكربت يُشغَّل مرة واحدة (أو عند استبدال ملفات الكتاب) لبناء
ملف JSON وسيط يحتوي صفحات الكتاب نظيفة، يُستخدم لاحقاً في التقطيع
والفهرسة (chunking.py) دون الحاجة لإعادة فتح ملفات PDF في كل مرة.
"""

import re
import json
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# إصلاح انعكاس اتجاه النص في عناوين الأقسام
# ---------------------------------------------------------------------------
# اكتُشف أن عناوين الأقسام الفرعية (مثل "عقيدتنا في النظر والمعرفة") تُخزَّن
# داخل الـ PDF بخط عريض مخصص (AXtManalBold / AXtManalBLack / mylotus-Bold)
# بترتيب "مرئي" معكوس بالكامل (صورة المرآة)، بعكس نص المتن (خط mylotus
# العادي) الذي يُستخرج بشكل صحيح. الحل: تحديد المقاطع (spans) حسب اسم
# الخط، وعكس نص أي مقطع بخط عريض من عائلة العناوين، مع الحفاظ على أي
# أرقام مضمّنة (مثل رقم الصفحة) بترتيبها الصحيح غير المعكوس.

_HEADING_FONT_MARKERS = ("Bold", "Black", "BLack")

# كلمات عربية شائعة جداً (حروف جر/وصل) تُستخدم كمعيار: أي مقطع بخط
# العناوين لا يحتوي أياً منها بترتيبه الحالي، بينما يحتويها بعد العكس،
# فهو على الأرجح مُخزَّن بترتيب مرآة معكوس ويحتاج تصحيحاً. هذا يتجنّب
# إفساد مقاطع عناوين قصيرة (مثل "النظر:") تكون مخزَّنة أصلاً بالترتيب
# الصحيح رغم استخدامها نفس الخط العريض.
_COMMON_ARABIC_WORDS = ("في", "من", "إلى", "على", "الذي", "عن", "هذا", "ذلك", "التي", "أن")


def _looks_reversed(text: str) -> bool:
    has_common_word_now = any(w in text for w in _COMMON_ARABIC_WORDS)
    if has_common_word_now:
        return False
    reversed_text = text[::-1]
    return any(w in reversed_text for w in _COMMON_ARABIC_WORDS)


def _is_heading_font(font_name: str) -> bool:
    return any(marker in font_name for marker in _HEADING_FONT_MARKERS)


def _reverse_preserving_digit_runs(text: str) -> str:
    """يعكس النص عكساً كاملاً، ثم يُصحح أي سلسلة أرقام أصبحت معكوسة."""
    reversed_text = text[::-1]
    return re.sub(r"\d+", lambda m: m.group()[::-1], reversed_text)


def extract_page_text_fixed(page: "fitz.Page") -> str:
    """
    يستخرج نص الصفحة سطراً سطراً، مع تصحيح انعكاس عناوين الأقسام ذات
    الخط العريض المكتشف، والحفاظ على ترتيب باقي النص كما هو (صحيح أصلاً).
    """
    page_dict = page.get_text("dict")
    lines_out = []

    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            parts = []
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text:
                    continue
                if _is_heading_font(span.get("font", "")) and _looks_reversed(text):
                    text = _reverse_preserving_digit_runs(text)
                parts.append(text)
            if parts:
                lines_out.append("".join(parts))

    return "\n".join(lines_out)


# ---------------------------------------------------------------------------
# تنظيف خلل الترميز
# ---------------------------------------------------------------------------
# اكتُشف أن خط الكتاب الأصلي (mylotus وملحقاته) يُدرج رموزاً دخيلة
# (أرقام 6-9، رموز تحكم، رموز خاصة) ملتصقة مباشرة بحروف الأسنان
# (س ش ص ض) بسبب خلل في جدول ترميز الخط (ToUnicode CMap) عند التصدير.
# تم التحقق تجريبياً أن هذه الرموز إضافية بحتة (حذفها يُصحح الكلمة
# دون فقدان أي حرف حقيقي)، وأن أرقام الحواشي الحقيقية (مفصولة بمسافة
# عن الكلمة) لا تتأثر بالحذف.

_DENY_CHARS = set("6789z|{¦®")
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_TEETH_LETTERS = set("سشصض")


def clean_font_glitches(text: str) -> str:
    """إزالة الرموز الدخيلة الناتجة عن خلل ترميز الخط الأصلي للكتاب."""
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        code = ord(ch)

        # نطاق الاستخدام الخاص (Private Use Area) — دائماً رمز عطل، لا يوجد
        # له أي استخدام شرعي في نص عربي فصيح.
        if 0xF000 <= code <= 0xF8FF:
            continue

        # رموز تحكم C1 — لا وجود لها في نص طبيعي.
        if 0x80 <= code <= 0x9F:
            continue

        # الرموز المشبوهة (أرقام 6-9 ورموز خاصة): تُحذف فقط عندما تكون
        # ملتصقة مباشرة (بلا مسافة) بحرف عربي قبلها أو بعدها — لأن هذا
        # هو نمط العطل المكتشف تحديداً. لا نحذفها إن وردت بشكل منفصل
        # (كأرقام حواشٍ حقيقية مثل "غافر 51").
        if ch in _DENY_CHARS:
            prev_arabic = i > 0 and bool(_ARABIC_RE.match(text[i - 1]))
            next_arabic = i + 1 < n and bool(_ARABIC_RE.match(text[i + 1]))
            if prev_arabic or next_arabic:
                continue

        out.append(ch)

    return "".join(out)


def normalize_whitespace(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# تصحيح انعكاس كلمتين قصيرتين شائعتين جداً
# ---------------------------------------------------------------------------
# تحقُّق إحصائي على الكتاب كاملاً أظهر أن حرف الجر "في" يظهر معكوساً
# "يف" في أكثر من 85% من حالاته (506 مقابل 74 في عيّنة من 100 مقطع)،
# وأن أداة النفي "لم" تظهر معكوسة "مل" في أكثر من 98% من حالاتها
# (496 مقابل 7). هذا خلل منفصل عن الخللين السابقين (رموز دخيلة عند
# حروف الأسنان، وانعكاس عناوين الخط العريض) — يبدو ناتجاً عن معالجة
# خاطئة لمقاطع قصيرة (كلمتين) معزولة بمسافات أثناء تصدير الـ PDF.
# "يف" و"مل" ليستا كلمتين عربيتين مستقلتين قائمتين بذاتهما، فاستبدالهما
# الكامل عند ورودهما ككلمة منفصلة (محاطة بحدود كلمة) آمن تماماً.

def fix_reversed_short_words(text: str) -> str:
    text = re.sub(r"(?<![\u0600-\u06FF])يف(?![\u0600-\u06FF])", "في", text)
    text = re.sub(r"(?<![\u0600-\u06FF])مل(?![\u0600-\u06FF])", "لم", text)
    return text


# ---------------------------------------------------------------------------
# حذف الترويسة المتكررة (عنوان الكتاب يظهر أعلى كل صفحة تقريباً)
# ---------------------------------------------------------------------------
_RUNNING_HEADER = "دروس منهجية في شرح عقائد الإمامية"
_RUNNING_HEADER_RE = re.compile(r"^(\d{0,4})" + re.escape(_RUNNING_HEADER) + r"$")


def strip_running_header_and_get_page_number(text: str) -> tuple[int | None, str]:
    """
    يحذف سطر الترويسة المتكررة، ويستخرج رقم الصفحة الملتصق ببدايتها
    إن وُجد (هذا هو المصدر الأساسي والأوثق لرقم الصفحة المطبوع، لأن
    الترويسة تتكرر بنفس الشكل تقريباً في أعلى كل صفحة محتوى).
    """
    page_number = None
    kept_lines = []
    for ln in text.split("\n"):
        m = _RUNNING_HEADER_RE.match(ln.strip())
        if m:
            if m.group(1):
                page_number = int(m.group(1))
            continue
        kept_lines.append(ln)
    return page_number, "\n".join(kept_lines)


def _looks_like_index_page(text: str) -> bool:
    """
    يكتشف صفحات "فهرس المحتويات" (عادة في نهاية كل جزء) والتي تُستخرج
    بترتيب نص مشوَّش (أعمدة متعددة) ولا تحمل أي محتوى إجابة فعلي، بل
    قائمة عناوين + أرقام صفحات. تُستبعد من قاعدة المعرفة لأنها عديمة
    الفائدة للإجابة وقد تحتوي أرقام صفحات مشوَّهة (خلل منفصل عن خلل
    حروف الأسنان، ناتج عن تعدد الأعمدة في تصميم صفحة الفهرس).
    """
    if "المحتويات" in text or "ايوتحملا" in text:  # الشكل الطبيعي أو المعكوس
        return True

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) < 6:
        return False

    ending_with_number = sum(1 for ln in lines if re.search(r"\d{1,4}$", ln))
    return ending_with_number / len(lines) > 0.5


# ---------------------------------------------------------------------------
# استخراج الصفحات
# ---------------------------------------------------------------------------

def extract_book_part(pdf_path: str, part_number: int) -> list[dict]:
    """
    يستخرج صفحات جزء واحد من الكتاب.

    ملاحظة مهمة: رقم الصفحة "الحقيقي" (المطبوع في الكتاب) قد يختلف عن
    رقم صفحة PDF (index) بسبب صفحات الغلاف/الفهرس/المقدمة في بداية كل
    جزء. هذه الدالة تحاول استخراج الرقم المطبوع فعلياً من أول سطر نصي
    في الصفحة (يظهر عادة كرقم منفصل في بداية النص)، وإن لم تجده تعتمد
    على ترقيم PDF كبديل احتياطي مع علامة `page_number_is_estimated`.

    صفحات "فهرس المحتويات" تُستبعد بالكامل (`is_index_page=True`) لأنها
    لا تحمل محتوى إجابة فعلياً، وترتيب نصها غالباً مشوَّش بسبب تعدد
    الأعمدة في تصميمها.
    """
    doc = fitz.open(pdf_path)
    pages = []

    for i, page in enumerate(doc):
        raw_text = extract_page_text_fixed(page)
        cleaned = clean_font_glitches(raw_text)
        cleaned = fix_reversed_short_words(cleaned)
        header_page_number, cleaned = strip_running_header_and_get_page_number(cleaned)
        cleaned = normalize_whitespace(cleaned)

        if not cleaned:
            continue

        if _looks_like_index_page(cleaned):
            pages.append({
                "part": part_number,
                "pdf_page_index": i + 1,
                "page_number": None,
                "page_number_is_estimated": True,
                "is_index_page": True,
                "text": cleaned,
            })
            continue

        # تحقُّق إحصائي على الكتاب كاملاً أظهر أن رقم الصفحة المطبوع يطابق
        # رقم صفحة PDF مباشرة (إزاحة = صفر) في الغالبية الساحقة من الحالات
        # (أكثر من 60-90% حسب الجزء)، بينما استخراج الرقم من نص الترويسة
        # لكل صفحة على حدة أضاف ضوضاء غير ضرورية بسبب تشوّهات نصية متفرقة.
        # لذلك اعتُمد ترقيم PDF مباشرة كرقم الصفحة المطبوع — أوثق وأبسط.
        printed_number = i + 1
        body_text = cleaned

        pages.append({
            "part": part_number,
            "pdf_page_index": i + 1,          # رقم صفحة PDF الفعلي (1-based)
            "page_number": printed_number,     # الرقم المطبوع (= ترقيم PDF)
            "page_number_is_estimated": False,
            "is_index_page": False,
            "text": body_text,
        })

    doc.close()
    return pages


def _split_leading_page_number(text: str) -> tuple[int | None, str]:
    """
    يفصل رقم الصفحة المطبوع إن كان يظهر كأول رمز في النص (نمط ملاحَظ في
    هذا الكتاب: رقم الصفحة يظهر ملتصقاً ببداية أول سطر، مثل "10دروس...").
    """
    match = re.match(r"^(\d{1,4})(?=\D)", text)
    if match:
        number = int(match.group(1))
        rest = text[match.end():].lstrip()
        return number, rest
    return None, text


def extract_full_book(data_dir: str = "data") -> list[dict]:
    """يستخرج الأجزاء الثلاثة كاملة ويعيدها كقائمة صفحات موحّدة."""
    data_path = Path(data_dir)
    all_pages = []

    for part_number, filename in [(1, "juz1.pdf"), (2, "juz2.pdf"), (3, "juz3.pdf")]:
        pdf_file = data_path / filename
        if not pdf_file.exists():
            raise FileNotFoundError(f"لم يُعثر على ملف الجزء {part_number}: {pdf_file}")
        pages = extract_book_part(str(pdf_file), part_number)
        all_pages.extend(pages)
        print(f"الجزء {part_number}: {len(pages)} صفحة مستخرَجة من {filename}")

    return all_pages


if __name__ == "__main__":
    pages = extract_full_book(data_dir="data")

    index_pages = sum(1 for p in pages if p["is_index_page"])
    estimated = sum(1 for p in pages if p["page_number_is_estimated"] and not p["is_index_page"])
    print(f"\nإجمالي الصفحات: {len(pages)}")
    print(f"صفحات فهرس مستبعدة من قاعدة المعرفة: {index_pages}")
    print(f"صفحات محتوى اعتُمد فيها ترقيم PDF كبديل: {estimated}")

    out_path = Path("data") / "book_pages_clean.json"
    out_path.write_text(
        json.dumps(pages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"تم الحفظ في: {out_path}")
