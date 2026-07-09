"""
app/ai.py
----------
يبني الإجابة من أفضل مقطع مطابق فقط (وليس دمج مقاطع متعددة)، حتى يبقى
الاستشهاد (كتاب + جزء + صفحة) مضموناً 100% من بيانات المقطع نفسه —
وليس من نص يخرجه DeepSeek، لتفادي أي استشهاد خاطئ أو مُختلَق.

الأسلوب: اقتباس شبه حرفي من نص المقطع، مع جملة ربط بسيطة فقط، وليس
تلخيصاً حراً — لأن الدقة اللفظية في نص عقائدي أهم من السلاسة.
"""

from openai import OpenAI

from app.config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, NO_ANSWER_MESSAGE
from app.search import hybrid_search, is_confident_direct_match
from app.chunking import citation_label

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")


SYSTEM_INSTRUCTION = """
أنت مساعد يجيب حصراً من نص مقتطف مرفق من كتاب عقائدي معتمد.

قواعد صارمة:
1. أجب فقط بناءً على النص المرفق أدناه، ولا تضف أي معلومة من خارجه.
2. أسلوب الإجابة: اقتباس شبه حرفي من النص، مع جملة ربط قصيرة فقط
   لتقديم الاقتباس (مثال: "يذكر الكتاب أن..." ثم الاقتباس). لا تُعِد
   صياغة المعنى بحرية ولا تُلخِّص بأسلوبك الخاص.
3. إن لم يُجب النص المرفق عن السؤال بوضوح، اكتب فقط الكلمة: NO_ANSWER
   (بدون أي إضافة)، ولا تحاول الاجتهاد أو الاستنتاج من خارج النص.
4. لا تذكر أبداً كلمات مثل: قاعدة بيانات، مقطع، chunk، embedding،
   PostgreSQL، أو أي مصطلح تقني. لا تذكر اسم الكتاب أو رقم الصفحة —
   هذا سيُضاف تلقائياً بعد إجابتك.
5. لا تُقدّم فتوى شخصية ولا رأياً خاصاً بك؛ أنت ناقل لما ورد في النص فقط.
""".strip()


def answer_question(user_id: int, question: str, chunks: list[dict]) -> tuple[str, str]:
    """
    يُرجع (نص_الإجابة, نوع_المسار) حيث نوع_المسار من: 'no_chunks' /
    'no_answer' / 'answered'.
    """
    if not chunks:
        return NO_ANSWER_MESSAGE, "no_chunks"

    results = hybrid_search(question, chunks, top_k=3)
    if not results: # قمنا بإلغاء شرط is_confident_direct_match
        return NO_ANSWER_MESSAGE, "no_answer"

    best = results[0]

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": f"{SYSTEM_INSTRUCTION}\n\n=== النص المرفق ===\n{best['text']}\n=== نهاية النص ==="},
            {"role": "user", "content": question},
        ],
        temperature=0.0,
        max_tokens=500,
    )

    answer = (response.choices[0].message.content or "").strip()

    if not answer or answer == "NO_ANSWER" or "NO_ANSWER" in answer:
        return NO_ANSWER_MESSAGE, "no_answer"

    citation = citation_label(best)
    final_answer = f"{answer}\n\n📖 المصدر: {citation}"
    return final_answer, "answered"
