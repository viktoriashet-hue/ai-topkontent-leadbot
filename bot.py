import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from config import BOT_TOKEN, ADMIN_IDS, SECRET_WORD, GIFT_LINK, ADMIN_CHAT_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States
WAITING_EMAIL = 1

def get_db():
    conn = sqlite3.connect("leads.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            email TEXT,
            joined_at TEXT,
            received_gift INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            sent_at TEXT,
            sent_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def save_lead(telegram_id, username, first_name, email):
    conn = get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO leads (telegram_id, username, first_name, email, joined_at, received_gift)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (telegram_id, username or "", first_name or "", email, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
    finally:
        conn.close()

def get_all_leads():
    conn = get_db()
    rows = conn.execute("SELECT * FROM leads ORDER BY joined_at DESC").fetchall()
    conn.close()
    return rows

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE joined_at LIKE ?",
        (datetime.now().strftime("%Y-%m-%d") + "%",)
    ).fetchone()[0]
    conn.close()
    return total, today

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Напиши кодовое слово, чтобы получить подарок 🎁",
        parse_mode="HTML"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    if text == SECRET_WORD.lower():
        await update.message.reply_text(
            "🎉 Верно! Ты в одном шаге от подарка.\n\n"
            "📧 Напиши свой <b>email</b>, чтобы я отправил тебе ссылку:",
            parse_mode="HTML"
        )
        return WAITING_EMAIL

    # If admin command in regular message
    if update.effective_user.id in ADMIN_IDS and text.startswith("/"):
        return ConversationHandler.END

    await update.message.reply_text(
        "🤔 Не знаю такого слова. Попробуй ещё раз!\n"
        "Если нужна помощь — напиши /start"
    )
    return ConversationHandler.END

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    user = update.effective_user

    # Basic email validation
    if "@" not in email or "." not in email.split("@")[-1]:
        await update.message.reply_text(
            "⚠️ Кажется, email введён неверно. Попробуй ещё раз:"
        )
        return WAITING_EMAIL

    # Save to DB
    save_lead(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        email=email
    )

    # Send gift
    await update.message.reply_text(
        f"✅ Отлично!\n\n"
        f"🎁 Вот твой подарок:\n{GIFT_LINK}\n\n"
        f"Сохрани ссылку — она только для тебя 💛",
        disable_web_page_preview=False
    )

    # Notify admin
    if ADMIN_CHAT_ID:
        try:
            tg_link = f"@{user.username}" if user.username else f"id{user.id}"
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"🔔 <b>Новый лид!</b>\n"
                     f"👤 {user.first_name} ({tg_link})\n"
                     f"📧 {email}\n"
                     f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify admin: {e}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Хорошо, отменил. Напиши /start чтобы начать заново.")
    return ConversationHandler.END

# ─── ADMIN COMMANDS ───────────────────────────────────────────

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Нет доступа.")
            return
        return await func(update, context)
    return wrapper

@admin_only
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total, today = get_stats()
    leads = get_all_leads()
    last5 = leads[:5]

    text = (
        f"📊 <b>Статистика базы</b>\n\n"
        f"👥 Всего лидов: <b>{total}</b>\n"
        f"📅 Сегодня: <b>{today}</b>\n\n"
    )

    if last5:
        text += "🕐 <b>Последние 5:</b>\n"
        for r in last5:
            tg = f"@{r['username']}" if r['username'] else f"id{r['telegram_id']}"
            text += f"• {r['first_name']} ({tg}) — {r['email']} — {r['joined_at']}\n"

    keyboard = [[InlineKeyboardButton("📨 Сделать рассылку", callback_data="start_broadcast")]]
    await update.message.reply_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@admin_only
async def admin_broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "📨 Использование:\n"
            "<code>/broadcast Привет! Вот новый материал: https://...</code>",
            parse_mode="HTML"
        )
        return

    message_text = " ".join(args)
    await do_broadcast(update, context, message_text)

async def do_broadcast(update, context, message_text):
    leads = get_all_leads()
    if not leads:
        await update.message.reply_text("📭 База пуста, некому отправлять.")
        return

    sent = 0
    failed = 0
    status_msg = await update.message.reply_text(f"📤 Начинаю рассылку на {len(leads)} человек...")

    for lead in leads:
        try:
            await context.bot.send_message(
                chat_id=lead["telegram_id"],
                text=message_text,
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    # Save broadcast to DB
    conn = get_db()
    conn.execute(
        "INSERT INTO broadcasts (message, sent_at, sent_count) VALUES (?, ?, ?)",
        (message_text, datetime.now().strftime("%Y-%m-%d %H:%M"), sent)
    )
    conn.commit()
    conn.close()

    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_broadcast" and query.from_user.id in ADMIN_IDS:
        await query.message.reply_text(
            "📝 Напиши текст рассылки командой:\n"
            "<code>/broadcast Твой текст здесь</code>",
            parse_mode="HTML"
        )

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            WAITING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("broadcast", admin_broadcast_cmd))
    app.add_handler(conv)

    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
