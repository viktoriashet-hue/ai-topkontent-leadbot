"""
@ai_topkontentbot — Lead Bot
Сбор контактов в обмен на подарок
"""

import logging
import asyncio
import os
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8142618101:AAGpKeRBP6oQrVUxIMhMBkQAahhl11ZIkyA")
ADMIN_IDS = [327487258]

# States
WAITING_CONSENT = 1
WAITING_KEYWORD = 2
WAITING_EMAIL = 3

# Admin states
ADMIN_SET_KEYWORD = 10
ADMIN_SET_GIFT = 11
ADMIN_BROADCAST = 12

# ─── DATABASE ────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect("leads.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            first_name TEXT,
            email TEXT,
            keyword TEXT,
            joined_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE,
            gift_link TEXT,
            created_at TEXT,
            is_active INTEGER DEFAULT 1
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
    # Default keyword if none exist
    existing = conn.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
    if existing == 0:
        conn.execute("""
            INSERT INTO keywords (word, gift_link, created_at, is_active)
            VALUES (?, ?, ?, 1)
        """, ("подарок", "https://your-gift-link.com", datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def get_keywords():
    conn = get_db()
    rows = conn.execute("SELECT * FROM keywords WHERE is_active = 1").fetchall()
    conn.close()
    return rows

def get_gift_by_keyword(word):
    conn = get_db()
    row = conn.execute(
        "SELECT gift_link FROM keywords WHERE LOWER(word) = LOWER(?) AND is_active = 1",
        (word.strip(),)
    ).fetchone()
    conn.close()
    return row["gift_link"] if row else None

def add_keyword(word, gift_link):
    conn = get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO keywords (word, gift_link, created_at, is_active)
            VALUES (?, ?, ?, 1)
        """, (word.strip().lower(), gift_link, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        return True
    except Exception as e:
        logger.error(e)
        return False
    finally:
        conn.close()

def deactivate_keyword(word):
    conn = get_db()
    conn.execute("UPDATE keywords SET is_active = 0 WHERE LOWER(word) = LOWER(?)", (word,))
    conn.commit()
    conn.close()

def save_lead(telegram_id, username, first_name, email, keyword):
    conn = get_db()
    conn.execute("""
        INSERT INTO leads (telegram_id, username, first_name, email, keyword, joined_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (telegram_id, username or "", first_name or "", email, keyword, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def already_got_gift(telegram_id, keyword):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM leads WHERE telegram_id = ? AND LOWER(keyword) = LOWER(?)",
        (telegram_id, keyword)
    ).fetchone()
    conn.close()
    return row is not None

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
    by_keyword = conn.execute(
        "SELECT keyword, COUNT(*) as cnt FROM leads GROUP BY keyword ORDER BY cnt DESC"
    ).fetchall()
    broadcasts = conn.execute("SELECT COUNT(*) FROM broadcasts").fetchone()[0]
    conn.close()
    return {"total": total, "today": today, "by_keyword": by_keyword, "broadcasts": broadcasts}

# ─── USER FLOW ───────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("✅ Принимаю условия", callback_data="consent_yes")],
        [InlineKeyboardButton("❌ Нет, не согласна", callback_data="consent_no")],
    ]
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        f"Этот бот собирает контакты и отправляет полезные материалы.\n\n"
        f"📌 Нажимая <b>«Принимаю условия»</b>, ты соглашаешься получать "
        f"сообщения и рассылки от этого бота.\n\n"
        f"Продолжим?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return WAITING_CONSENT

async def consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "consent_yes":
        await query.edit_message_text(
            "🎉 Отлично!\n\n"
            "Напиши кодовое слово, чтобы получить подарок 🎁",
            parse_mode="HTML"
        )
        return WAITING_KEYWORD
    else:
        await query.edit_message_text(
            "Хорошо, понял. Если передумаешь — напиши /start 👋"
        )
        return ConversationHandler.END

async def handle_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    gift_link = get_gift_by_keyword(text)

    if gift_link:
        # Check if already received this gift
        if already_got_gift(update.effective_user.id, text):
            await update.message.reply_text(
                f"🎁 Ты уже получал(а) подарок по этому слову!\n\n"
                f"Вот ссылка снова: {gift_link}"
            )
            return ConversationHandler.END

        context.user_data["keyword"] = text
        context.user_data["gift_link"] = gift_link
        await update.message.reply_text(
            "✅ Верно! Почти готово.\n\n"
            "📧 Напиши свой <b>email</b> — и сразу получишь подарок:",
            parse_mode="HTML"
        )
        return WAITING_EMAIL
    else:
        await update.message.reply_text(
            "🤔 Не знаю такого кодового слова. Попробуй ещё раз!\n"
            "Или напиши /start чтобы начать заново."
        )
        return WAITING_KEYWORD

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    user = update.effective_user

    if "@" not in email or "." not in email.split("@")[-1]:
        await update.message.reply_text(
            "⚠️ Похоже email введён неверно. Попробуй ещё раз:\n"
            "Пример: name@gmail.com"
        )
        return WAITING_EMAIL

    keyword = context.user_data.get("keyword", "")
    gift_link = context.user_data.get("gift_link", "")

    save_lead(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        email=email,
        keyword=keyword
    )

    await update.message.reply_text(
        f"🎁 <b>Вот твой подарок!</b>\n\n"
        f"{gift_link}\n\n"
        f"Сохрани ссылку 💛\n"
        f"Если будут вопросы — всегда здесь!",
        parse_mode="HTML"
    )

    # Notify admin
    for admin_id in ADMIN_IDS:
        try:
            tg_link = f"@{user.username}" if user.username else f"id{user.id}"
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 <b>Новый лид!</b>\n"
                     f"👤 {user.first_name} ({tg_link})\n"
                     f"📧 {email}\n"
                     f"🔑 Слово: <b>{keyword}</b>\n"
                     f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа {admin_id}: {e}")

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменил. Напиши /start чтобы начать заново.")
    return ConversationHandler.END

# ─── ADMIN COMMANDS ───────────────────────────────────────────

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    stats = get_stats()
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего лидов: <b>{stats['total']}</b>\n"
        f"📅 Сегодня: <b>{stats['today']}</b>\n"
        f"📨 Рассылок: <b>{stats['broadcasts']}</b>\n\n"
    )
    if stats["by_keyword"]:
        text += "🔑 <b>По кодовым словам:</b>\n"
        for row in stats["by_keyword"]:
            text += f"  • <b>{row['keyword']}</b> — {row['cnt']} чел.\n"
    text += "\n<b>Команды:</b>\n"
    text += "/addkeyword — добавить кодовое слово\n"
    text += "/keywords — список активных слов\n"
    text += "/delkeyword — удалить слово\n"
    text += "/broadcast — рассылка по базе\n"
    text += "/leads — последние 10 лидов"
    await update.message.reply_text(text, parse_mode="HTML")

async def admin_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    leads = get_all_leads()[:10]
    if not leads:
        await update.message.reply_text("📭 База пуста.")
        return
    text = f"👥 <b>Последние {len(leads)} лидов:</b>\n\n"
    for i, lead in enumerate(leads, 1):
        tg = f"@{lead['username']}" if lead['username'] else f"id{lead['telegram_id']}"
        text += f"{i}. {lead['first_name']} ({tg})\n   📧 {lead['email']} | 🔑 {lead['keyword']} | 🕐 {lead['joined_at']}\n\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def admin_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    keywords = get_keywords()
    if not keywords:
        await update.message.reply_text("Активных кодовых слов нет. Добавь через /addkeyword")
        return
    text = "🔑 <b>Активные кодовые слова:</b>\n\n"
    for kw in keywords:
        text += f"• <b>{kw['word']}</b>\n  🎁 {kw['gift_link']}\n  📅 {kw['created_at']}\n\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def admin_addkeyword_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text(
        "🔑 Напиши новое кодовое слово:\n"
        "(например: <code>контент2024</code>)",
        parse_mode="HTML"
    )
    return ADMIN_SET_KEYWORD

async def admin_addkeyword_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_keyword"] = update.message.text.strip().lower()
    await update.message.reply_text(
        f"✅ Слово: <b>{context.user_data['new_keyword']}</b>\n\n"
        f"Теперь напиши ссылку на подарок для этого слова:",
        parse_mode="HTML"
    )
    return ADMIN_SET_GIFT

async def admin_addkeyword_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gift_link = update.message.text.strip()
    keyword = context.user_data.get("new_keyword", "")

    if add_keyword(keyword, gift_link):
        await update.message.reply_text(
            f"✅ <b>Добавлено!</b>\n\n"
            f"🔑 Слово: <b>{keyword}</b>\n"
            f"🎁 Подарок: {gift_link}\n\n"
            f"Теперь пользователи могут написать это слово и получить подарок!",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ Ошибка при добавлении. Попробуй ещё раз.")
    return ConversationHandler.END

async def admin_delkeyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "Использование: <code>/delkeyword слово</code>",
            parse_mode="HTML"
        )
        return
    word = " ".join(args).strip().lower()
    deactivate_keyword(word)
    await update.message.reply_text(f"✅ Слово <b>{word}</b> деактивировано.", parse_mode="HTML")

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    stats = get_stats()
    await update.message.reply_text(
        f"📨 <b>Рассылка по базе</b>\n\n"
        f"В базе: <b>{stats['total']}</b> человек\n\n"
        f"Напиши текст сообщения.\n"
        f"Поддерживается HTML: <code>&lt;b&gt;жирный&lt;/b&gt;</code>, <code>&lt;a href='...'&gt;ссылка&lt;/a&gt;</code>\n\n"
        f"Или /cancel для отмены:",
        parse_mode="HTML"
    )
    return ADMIN_BROADCAST

async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()
    leads = get_all_leads()

    if not leads:
        await update.message.reply_text("📭 База пуста.")
        return ConversationHandler.END

    status = await update.message.reply_text(f"📤 Отправляю {len(leads)} людям...")

    sent = 0
    failed = 0
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

    conn = get_db()
    conn.execute(
        "INSERT INTO broadcasts (message, sent_at, sent_count) VALUES (?, ?, ?)",
        (message_text, datetime.now().strftime("%Y-%m-%d %H:%M"), sent)
    )
    conn.commit()
    conn.close()

    await status.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        parse_mode="HTML"
    )
    return ConversationHandler.END

# ─── MAIN ────────────────────────────────────────────────────

async def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # User conversation
    user_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_CONSENT: [CallbackQueryHandler(consent_callback, pattern="^consent_")],
            WAITING_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyword)],
            WAITING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    # Admin add keyword conversation
    addkw_conv = ConversationHandler(
        entry_points=[CommandHandler("addkeyword", admin_addkeyword_start)],
        states={
            ADMIN_SET_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addkeyword_word)],
            ADMIN_SET_GIFT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addkeyword_gift)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    # Admin broadcast conversation
    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", admin_broadcast_start)],
        states={
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(user_conv)
    app.add_handler(addkw_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("leads", admin_leads))
    app.add_handler(CommandHandler("keywords", admin_keywords))
    app.add_handler(CommandHandler("delkeyword", admin_delkeyword))

    logger.info("✅ Бот запущен — @ai_topkontentbot")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()
    await app.stop()

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
