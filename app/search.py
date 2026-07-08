"""
app/search.py
--------------
بحث Hybrid: يجمع تشابهاً لفظياً بسيطاً (تقاطع كلمات، بلا تكلفة) مع
تشابه دلالي (embeddings، يفهم صياغات لم تُكتب حرفياً في الكتاب، بما
في ذلك اللهجة العراقية). الدرجة النهائية = مزيج الاثنين، ولا يُعتبر
أي مقطع "تطابقاً واثقاً" إلا إذا اتفقت الدرجتان معاً — هذا يُغلق
الثغرة التي اكتُشفت في بوت المعهد (حيث كان التطابق اللفظي وحده كافياً
للرد المباشر بلا أي تحقق مضاد للاختراع).
"""

import re
from app.embedding import embed_query, cosine_similarity

_WORD_RE = re.compile(r"[\u0600-\u06FF]+")


def _lexical_score(query_words: set[str], chunk_text: str) -> float:
    chunk_words = set(_WORD_RE.findall(chunk_text))
    if not query_words:
        return 0.0
    overlap = query_words & chunk_words
    return len(overlap) / len(query_words)


def hybrid_search(query: str, chunks: list[dict], top_k: int = 4) -> list[dict]:
    """
    يُرجع أفضل top_k مقاطع مرتبة حسب الدرجة الهجينة، كل مقطع مع درجاته
    التفصيلية (lexical_score, semantic_score, hybrid_score) لاتخاذ قرار
    لاحق (رد مباشر أم استدعاء DeepSeek).
    """
    query_words = set(_WORD_RE.findall(query))
    query_vector = embed_query(query)

    scored = []
    for chunk in chunks:
        lexical = _lexical_score(query_words, chunk["text"])
        semantic = cosine_similarity(query_vector, chunk["embedding"])
        hybrid = 0.4 * lexical + 0.6 * semantic
        scored.append({**chunk, "lexical_score": lexical, "semantic_score": semantic, "hybrid_score": hybrid})

    scored.sort(key=lambda c: c["hybrid_score"], reverse=True)
    return scored[:top_k]


# عتبات القرار — قيم أولية غير مقيسة بمجموعة اختبار حقيقية بعد (نفس
# الملاحظة المسجَّلة في مراجعة بوت المعهد)؛ يجب ضبطها لاحقاً بعد جمع
# أسئلة حقيقية من الاستخدام الفعلي.
DIRECT_ANSWER_SEMANTIC_THRESHOLD = 0.78
DIRECT_ANSWER_LEXICAL_THRESHOLD = 0.35


def is_confident_direct_match(top_result: dict) -> bool:
    """
    لا يُعتبر تطابقاً واثقاً إلا إذا اتفقت الدرجتان معاً (لفظي ودلالي)،
    تفادياً لاعتماد رد مباشر بلا مراجعة على مطابقة كلمات سطحية فقط.
    """
    return (
        top_result["semantic_score"] >= DIRECT_ANSWER_SEMANTIC_THRESHOLD
        and top_result["lexical_score"] >= DIRECT_ANSWER_LEXICAL_THRESHOLD
    )
