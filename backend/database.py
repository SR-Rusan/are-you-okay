import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "care_memory.db"))

def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            kin_name TEXT NOT NULL,
            kin_relation TEXT NOT NULL,
            kin_phone TEXT NOT NULL,
            consent_status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'consented', 'declined'
            consent_timestamp TEXT,
            last_session_summary TEXT DEFAULT '',
            avg_reply_length REAL DEFAULT 35.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT NOT NULL DEFAULT 'active', -- 'active', 'completed', 'declined'
            summary TEXT DEFAULT '',
            distress_flagged INTEGER DEFAULT 0,
            distress_reason TEXT DEFAULT '',
            matched_rule TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    # Session message turns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            sender TEXT NOT NULL, -- 'ai' or 'user'
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        )
    """)

    # Flagged alerts history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            matched_rule TEXT NOT NULL,
            reason TEXT NOT NULL,
            sms_text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)

    conn.commit()

    # Seed initial test personas if database is freshly created
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    if count == 0:
        seed_sample_users(cursor)
        conn.commit()

    conn.close()

def seed_sample_users(cursor: sqlite3.Cursor) -> None:
    now = datetime.now().isoformat()
    samples = [
        (
            "user_new",
            "ছবি বেগম (Chhobi Begum)",
            "তানভীর আহমেদ",
            "ছেলে (প্রবাসী - টরন্টো, কানাডা)",
            "+1-416-555-0199",
            "pending",
            None,
            "",
            30.0,
            now,
            now
        ),
        (
            "user_fatema",
            "বেগম ফাতেমা (Fatema Begum)",
            "মাহমুদুল হাসান",
            "ছেলে (প্রবাসী - লন্ডন, যুক্তরাজ্য)",
            "+44-7700-900123",
            "consented",
            now,
            "গতবার তিনি জানিয়েছিলেন ডান হাঁটুতে বেশ ব্যথা করছিল আর রাতে ঘুমে একটু সমস্যা হচ্ছিল। ডাক্তার দেখানোর কথা ছিল।",
            38.0,
            now,
            now
        ),
        (
            "user_rafiq",
            "রফিকুল ইসলাম (Rafiqul Islam)",
            "ফারহানা হক",
            "মেয়ে (প্রবাসী - সিডনি, অস্ট্রেলিয়া)",
            "+61-491-570156",
            "consented",
            now,
            "গত সেশনে চাচা জানিয়েছিলেন নাতিদের খুব মিস করছেন, তবে সকালে পার্কে হেঁটেছিলেন। ব্লাড প্রেশারের ওষুধ নিয়মিত খাচ্ছেন।",
            42.0,
            now,
            now
        )
    ]

    cursor.executemany("""
        INSERT INTO users (
            user_id, name, kin_name, kin_relation, kin_phone,
            consent_status, consent_timestamp, last_session_summary,
            avg_reply_length, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, samples)

def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def list_users() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY created_at ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_user_consent(user_id: str, status: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE users
        SET consent_status = ?, consent_timestamp = ?, updated_at = ?
        WHERE user_id = ?
    """, (status, now, now, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def update_user_summary(user_id: str, summary: str, new_reply_length: Optional[float] = None) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    if new_reply_length is not None and new_reply_length > 0:
        cursor.execute("""
            UPDATE users
            SET last_session_summary = ?,
                avg_reply_length = (avg_reply_length * 0.7 + ? * 0.3),
                updated_at = ?
            WHERE user_id = ?
        """, (summary, new_reply_length, now, user_id))
    else:
        cursor.execute("""
            UPDATE users
            SET last_session_summary = ?, updated_at = ?
            WHERE user_id = ?
        """, (summary, now, user_id))
    conn.commit()
    conn.close()

def reset_user(user_id: str) -> bool:
    """Resets user data for quick testing and demonstrations."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    if user_id == "user_new":
        cursor.execute("""
            UPDATE users
            SET consent_status = 'pending', consent_timestamp = NULL,
                last_session_summary = '', updated_at = ?
            WHERE user_id = ?
        """, (now, user_id))
    elif user_id == "user_fatema":
        cursor.execute("""
            UPDATE users
            SET consent_status = 'consented', consent_timestamp = ?,
                last_session_summary = 'গতবার তিনি জানিয়েছিলেন ডান হাঁটুতে বেশ ব্যথা করছিল আর রাতে ঘুমে একটু সমস্যা হচ্ছিল। ডাক্তার দেখানোর কথা ছিল।',
                updated_at = ?
            WHERE user_id = ?
        """, (now, now, user_id))
    elif user_id == "user_rafiq":
        cursor.execute("""
            UPDATE users
            SET consent_status = 'consented', consent_timestamp = ?,
                last_session_summary = 'গত সেশনে চাচা জানিয়েছিলেন নাতিদের খুব মিস করছেন, তবে সকালে পার্কে হেঁটেছিলেন। ব্লাড প্রেশারের ওষুধ নিয়মিত খাচ্ছেন।',
                updated_at = ?
            WHERE user_id = ?
        """, (now, now, user_id))
    else:
        cursor.execute("""
            UPDATE users
            SET consent_status = 'pending', consent_timestamp = NULL,
                last_session_summary = '', updated_at = ?
            WHERE user_id = ?
        """, (now, user_id))
    conn.commit()
    conn.close()
    return True

def create_session(session_id: str, user_id: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO sessions (session_id, user_id, started_at, status)
        VALUES (?, ?, ?, 'active')
    """, (session_id, user_id, now))
    conn.commit()
    conn.close()

def log_message(session_id: str, user_id: str, sender: str, text: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO messages (session_id, user_id, sender, text, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, user_id, sender, text, now))
    conn.commit()
    conn.close()

def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sender, text, timestamp FROM messages
        WHERE session_id = ? ORDER BY id ASC
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def finish_session(
    session_id: str,
    status: str,
    summary: str,
    distress_flagged: bool,
    distress_reason: str,
    matched_rule: str
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE sessions
        SET ended_at = ?, status = ?, summary = ?,
            distress_flagged = ?, distress_reason = ?, matched_rule = ?
        WHERE session_id = ?
    """, (now, status, summary, 1 if distress_flagged else 0, distress_reason, matched_rule, session_id))
    conn.commit()
    conn.close()

def record_alert(alert_id: str, user_id: str, session_id: str, matched_rule: str, reason: str, sms_text: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO alerts (id, user_id, session_id, matched_rule, reason, sms_text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (alert_id, user_id, session_id, matched_rule, reason, sms_text, now))
    conn.commit()
    conn.close()

def get_recent_alerts(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, u.name as user_name, u.kin_name, u.kin_relation, u.kin_phone
        FROM alerts a
        JOIN users u ON a.user_id = u.user_id
        ORDER BY a.timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
