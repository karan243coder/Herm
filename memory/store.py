import sqlite3
import os
import logging

logger = logging.getLogger(__name__)
DB_PATH = "hermes_agent_v2.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Persona & custom identity per chat
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_personas (
            chat_id INTEGER PRIMARY KEY,
            custom_identity TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Conversation history
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Cross-session long-term memory (facts & preferences)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS long_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            fact_key TEXT,
            fact_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Kanban / Todo tasks
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kanban_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            task TEXT,
            status TEXT DEFAULT 'todo',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Cron scheduled tasks & reminders
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cron_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            task_description TEXT,
            run_timestamp INTEGER,
            is_completed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_custom_identity(chat_id: int) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT custom_identity FROM chat_personas WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def set_custom_identity(chat_id: int, identity_text: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_personas (chat_id, custom_identity)
        VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET custom_identity = excluded.custom_identity
    """, (chat_id, identity_text))
    conn.commit()
    conn.close()

def add_history(chat_id: int, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO chat_history (chat_id, role, content) VALUES (?, ?, ?)", (chat_id, role, content))
    conn.commit()
    conn.close()

def fetch_history(chat_id: int, limit: int = 12):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT role, content FROM chat_history
        WHERE chat_id = ?
        ORDER BY id DESC LIMIT ?
    """, (chat_id, limit))
    rows = cur.fetchall()
    conn.close()
    rows.reverse()
    return [{"role": r[0], "content": r[1]} for r in rows]

def clear_history(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def reset_all(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_personas WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM long_term_memory WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM kanban_tasks WHERE chat_id = ?", (chat_id,))
    cur.execute("DELETE FROM cron_jobs WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def save_fact(chat_id: int, key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO long_term_memory (chat_id, fact_key, fact_value) VALUES (?, ?, ?)", (chat_id, key, value))
    conn.commit()
    conn.close()

def get_all_facts(chat_id: int) -> list[tuple[str, str]]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT fact_key, fact_value FROM long_term_memory WHERE chat_id = ?", (chat_id,))
    facts = cur.fetchall()
    conn.close()
    return facts
