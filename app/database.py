"""
app/database.py
-----------------
اتصال PostgreSQL وإدارة الجداول:
- book_chunks: مقاطع الكتاب النظيفة + بيانات الاستشهاد + المتجه الدلالي
- users / messages: نفس نمط بوت المعهد (إحصائيات استخدام بسيطة)
"""

import json
import psycopg2
import psycopg2.extras

from app.config import DATABASE_URL


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """ينشئ الجداول إن لم تكن موجودة. يُستدعى مرة عند إقلاع التطبيق."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS book_chunks (
                    chunk_id     INTEGER PRIMARY KEY,
                    part         INTEGER NOT NULL,
                    page_start   INTEGER NOT NULL,
                    page_end     INTEGER NOT NULL,
                    text         TEXT NOT NULL,
                    embedding    JSONB NOT NULL
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id      BIGINT PRIMARY KEY,
                    username     TEXT,
                    first_seen   TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id           SERIAL PRIMARY KEY,
                    user_id      BIGINT NOT NULL,
                    question     TEXT NOT NULL,
                    answer_path  TEXT NOT NULL,  -- 'direct' / 'deepseek' / 'no_answer'
                    created_at   TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()


def replace_all_chunks(chunks: list[dict]):
    """
    يستبدل محتوى قاعدة المعرفة بالكامل بمقاطع جديدة (يُستخدم عند إعادة
    بناء الفهرسة من ملفات الكتاب، مثلاً بعد استبدال ملفات PDF).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE book_chunks;")
            args = [
                (
                    c["chunk_id"], c["part"], c["page_start"], c["page_end"],
                    c["text"], json.dumps(c["embedding"]),
                )
                for c in chunks
            ]
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO book_chunks (chunk_id, part, page_start, page_end, text, embedding)
                   VALUES %s""",
                args,
            )
        conn.commit()


def load_all_chunks() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT chunk_id, part, page_start, page_end, text, embedding FROM book_chunks;")
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def log_message(user_id: int, question: str, answer_path: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (user_id, question, answer_path) VALUES (%s, %s, %s);",
                (user_id, question, answer_path),
            )
        conn.commit()


def register_user(user_id: int, username: str | None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users (user_id, username) VALUES (%s, %s)
                   ON CONFLICT (user_id) DO NOTHING;""",
                (user_id, username),
            )
        conn.commit()


def get_stats() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;")
            total_users = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM messages;")
            total_messages = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM messages WHERE created_at::date = CURRENT_DATE;")
            today_messages = cur.fetchone()[0]
    return {
        "total_users": total_users,
        "total_messages": total_messages,
        "today_messages": today_messages,
    }
