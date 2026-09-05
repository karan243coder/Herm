import time
import threading
import sqlite3
import logging

logger = logging.getLogger(__name__)
DB_PATH = "hermes_agent_v2.db"

def add_cron_job(chat_id: int, task_description: str, delay_seconds: int) -> str:
    target_time = int(time.time()) + delay_seconds
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cron_jobs (chat_id, task_description, run_timestamp)
        VALUES (?, ?, ?)
    """, (chat_id, task_description, target_time))
    conn.commit()
    conn.close()
    mins = delay_seconds // 60
    return f"Scheduled task: '{task_description}' will trigger in {mins} minutes."

def list_cron_jobs(chat_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, task_description, run_timestamp FROM cron_jobs WHERE chat_id = ? AND is_completed = 0", (chat_id,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return "No active scheduled reminders."
    now = int(time.time())
    res = []
    for r in rows:
        rem = max(0, r[2] - now) // 60
        res.append(f"• ID {r[0]}: {r[1]} (in ~{rem} mins)")
    return "⏰ Active Reminders:\n" + "\n".join(res)

def start_cron_worker(bot_instance):
    def worker():
        logger.info("Background Cron Scheduler started...")
        while True:
            try:
                now = int(time.time())
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT id, chat_id, task_description FROM cron_jobs WHERE is_completed = 0 AND run_timestamp <= ?", (now,))
                due_jobs = cur.fetchall()
                for job in due_jobs:
                    jid, cid, desc = job
                    try:
                        bot_instance.send_message(cid, f"⏰ *Hermes Scheduled Reminder:*\n\n_{desc}_", parse_mode="Markdown")
                        cur.execute("UPDATE cron_jobs SET is_completed = 1 WHERE id = ?", (jid,))
                        conn.commit()
                    except Exception as err:
                        logger.error(f"Failed to deliver cron job {jid}: {err}")
                conn.close()
            except Exception as e:
                logger.error(f"Cron worker error: {e}")
            time.sleep(15)

    threading.Thread(target=worker, daemon=True).start()
