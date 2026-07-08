"""
app/embedding.py
------------------
تمثيل دلالي محلي (بلا أي استدعاء API خارجي، تكلفة تشغيلية = صفر) باستخدام
fastembed (يعتمد ONNX Runtime، أخف بكثير من PyTorch/sentence-transformers
الكاملة). النموذج: paraphrase-multilingual-MiniLM-L12-v2 (~220 ميغابايت)،
يدعم العربية ضمن أكثر من 50 لغة، وهو الخيار الأخف المتاح فعلياً في
fastembed (multilingual-e5-small غير مدعوم حالياً في هذه المكتبة).
"""

import numpy as np
from fastembed import TextEmbedding

from app.config import EMBEDDING_MODEL

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """يحسب متجهات دلالية لقائمة نصوص (يُستخدم عند بناء الفهرسة)."""
    model = get_model()
    return [vec.tolist() for vec in model.embed(texts)]


def embed_query(text: str) -> list[float]:
    """يحسب متجه سؤال المستخدم اللحظي (استدعاء واحد فقط لكل سؤال)."""
    return embed_texts([text])[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
