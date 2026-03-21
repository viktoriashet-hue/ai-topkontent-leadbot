"""
Синхронный runner для рассылки из веб-панели.
"""
import sqlite3
import asyncio
from datetime import datetime
from telegram import Bot
from config import BOT_TOKEN

def get_db():
    conn = sqlite3.connect("leads.db")
    conn.row_factory = sqlite3.Row
    return conn

async def _send(message: str) -> int:
    bot = Bot(token=BOT_TOKEN)
    conn = get_db()
    leads = conn.execute("SELECT telegram_id FROM leads").fetchall()
    conn.close()

    sent = 0
    for lead in leads:
        try:
            await bot.send_message(
                chat_id=lead["telegram_id"],
                text=message,
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            pass

    # Save to DB
    conn = get_db()
    conn.execute(
        "INSERT INTO broadcasts (message, sent_at, sent_count) VALUES (?, ?, ?)",
        (message, datetime.now().strftime("%Y-%m-%d %H:%M"), sent)
    )
    conn.commit()
    conn.close()
    return sent

def send_broadcast_sync(message: str) -> int:
    return asyncio.run(_send(message))
