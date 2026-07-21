"""
@ai_topkontentbot — Lead Bot с PostgreSQL
"""

import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8142618101:AAGpKeRBP6oQrVUxIMhMBkQAahhl11ZIkyA")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:HkvsvVVSnPpCIrPMgsWXnSKMvYSSKhFl@postgres.railway.internal:5432/railway")
ADMIN_IDS = [327487258]

WAITING_CONSENT = 1
WAITING_KEYWORD = 2
WAITING_EMAIL = 3

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS leads (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT, username TEXT, first_name TEXT,
        email TEXT, keyword TEXT, joined_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS keywords (
        id SERIAL PRIMARY KEY,
        word TEXT UNIQUE, gift_link TEXT, created_at TEXT, is_active INTEGER DEFAULT 1)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS broadcasts (
        id SERIAL PRIMARY KEY,
        message TEXT, sent_at TEXT, sent_count INTEGER DEFAULT 0)""")
    cur.execute("SELECT COUNT(*) FROM keywords")
    count = cur.fetchone()["count"]
    if count == 0:
        cur.execute("INSERT INTO keywords (word, gift_link, created_at, is_active) VALUES (%s, %s, %s, 1)",
                    ("подарок", "https://your-gift-link.com", datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    cur.close()
    conn.close()

def get_keywords():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM keywords WHERE is_active = 1")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_gift_by_keyword(word):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT word, gift_link FROM keywords WHERE is_active = 1")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    word_lower = word.strip().lower()
    for row in rows:
        if row["word"].lower() == word_lower:
            return row["gift_link"]
    return None

def add_keyword(word, gift_link):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO keywords (word, gift_link, created_at, is_active) VALUES (%s, %s, %s, 1) ON CONFLICT (word) DO UPDATE SET gift_link=%s, is_active=1",
                    (word.strip().lower(), gift_link, datetime.now().strftime("%Y-%m-%d %H:%M"), gift_link))
        conn.commit()
        return True
    except Exception as e:
        logger.error(e)
        return False
    finally:
        cur.close()
        conn.close()

def deactivate_keyword(word):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, word FROM keywords WHERE is_active = 1")
    rows = cur.fetchall()
    word_lower = word.strip().lower()
    for row in rows:
        if row["word"].lower() == word_lower:
            cur.execute("UPDATE keywords SET is_active = 0 WHERE id = %s", (row["id"],))
            break
    conn.commit()
    cur.close()
    conn.close()

def save_lead(telegram_id, username, first_name, email, keyword):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO leads (telegram_id, username, first_name, email, keyword, joined_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (telegram_id, username or "", first_name or "", email, keyword, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    cur.close()
    conn.close()

def already_got_gift(telegram_id, keyword):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT keyword FROM leads WHERE telegram_id = %s", (telegram_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    keyword_lower = keyword.strip().lower()
    return any(r["keyword"].lower() == keyword_lower for r in rows)

def get_all_leads():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads ORDER BY joined_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM leads")
    total = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) FROM leads WHERE joined_at LIKE %s", (datetime.now().strftime("%Y-%m-%d") + "%",))
    today = cur.fetchone()["count"]
    cur.execute("SELECT keyword, COUNT(*) as cnt FROM leads GROUP BY keyword ORDER BY cnt DESC")
    by_keyword = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM broadcasts")
    broadcasts = cur.fetchone()["count"]
    cur.close()
    conn.close()
    return {"total": total, "today": today, "by_keyword": by_keyword, "broadcasts": broadcasts}

def admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
         InlineKeyboardButton("👥 База лидов", callback_data="admin_leads")],
        [InlineKeyboardButton("🔑 Кодовые слова", callback_data="admin_keywords"),
         InlineKeyboardButton("➕ Добавить слово", callback_data="admin_addkw")],
        [InlineKeyboardButton("📨 Сделать рассылку", callback_data="admin_broadcast")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in ADMIN_IDS:
        stats = get_stats()
        await update.message.reply_text(
            f"👑 <b>Панель управления</b>\n\n"
            f"👥 Лидов в базе: <b>{stats['total']}</b>\n"
            f"📅 Сегодня пришло: <b>{stats['today']}</b>\n"
            f"🔑 Активных слов: <b>{len(get_keywords())}</b>\n\nВыбери действие 👇",
            parse_mode="HTML", reply_markup=admin_menu_keyboard())
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton("✅ Принимаю условия", callback_data="consent_yes")],
        [InlineKeyboardButton("❌ Нет, спасибо", callback_data="consent_no")],
    ]
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\nЭтот бот отправляет полезные материалы по контенту.\n\n"
        f"📌 Нажимая <b>«Принимаю условия»</b>, ты соглашаешься получать сообщения и рассылки от этого бота.\n\nПродолжим?",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_CONSENT

async def consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "consent_yes":
        await query.edit_message_text("🎉 Отлично!\n\nНапиши кодовое слово, чтобы получить подарок 🎁")
        return WAITING_KEYWORD
    else:
        await query.edit_message_text("Хорошо! Если передумаешь — напиши /start 👋")
        return ConversationHandler.END

async def handle_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    gift_link = get_gift_by_keyword(text)
    if gift_link:
        if already_got_gift(update.effective_user.id, text):
            await update.message.reply_text(f"🎁 Ты уже получал(а) подарок по этому слову!\n\nВот ссылка снова: {gift_link}")
            return ConversationHandler.END
        context.user_data["keyword"] = text
        context.user_data["gift_link"] = gift_link
        await update.message.reply_text("✅ Верно! Почти готово.\n\n📧 Напиши свой <b>email</b> — и сразу получишь подарок:", parse_mode="HTML")
        return WAITING_EMAIL
    else:
        await update.message.reply_text("🤔 Не знаю такого кодового слова. Попробуй ещё раз!")
        return WAITING_KEYWORD

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    user = update.effective_user
    if "@" not in email or "." not in email.split("@")[-1]:
        await update.message.reply_text("⚠️ Похоже email введён неверно.\nПример: name@gmail.com")
        return WAITING_EMAIL
    keyword = context.user_data.get("keyword", "")
    gift_link = context.user_data.get("gift_link", "")
    save_lead(user.id, user.username, user.first_name, email, keyword)
    await update.message.reply_text(f"🎁 <b>Вот твой подарок!</b>\n\n{gift_link}\n\nСохрани ссылку 💛", parse_mode="HTML")
    for admin_id in ADMIN_IDS:
        try:
            tg_link = f"@{user.username}" if user.username else f"id{user.id}"
            await context.bot.send_message(chat_id=admin_id,
                text=f"🔔 <b>Новый лид!</b>\n👤 {user.first_name} ({tg_link})\n📧 {email}\n🔑 Слово: <b>{keyword}</b>\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа: {e}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["admin_state"] = None
    await update.message.reply_text("Отменил. Напиши /start чтобы начать заново.")
    return ConversationHandler.END

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMIN_IDS:
        return
    if query.data == "admin_stats":
        stats = get_stats()
        text = f"📊 <b>Статистика</b>\n\n👥 Всего: <b>{stats['total']}</b>\n📅 Сегодня: <b>{stats['today']}</b>\n📨 Рассылок: <b>{stats['broadcasts']}</b>\n"
        if stats["by_keyword"]:
            text += "\n🔑 <b>По кодовым словам:</b>\n"
            for row in stats["by_keyword"]:
                text += f"  • <b>{row['keyword']}</b> — {row['cnt']} чел.\n"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())
    elif query.data == "admin_leads":
        leads = get_all_leads()[:10]
        text = "📭 База пуста." if not leads else f"👥 <b>Последние {len(leads)} лидов:</b>\n\n" + "".join(
            f"{i}. {l['first_name']} (@{l['username'] or l['telegram_id']})\n   📧 {l['email']} | 🔑 {l['keyword']} | {l['joined_at']}\n\n"
            for i, l in enumerate(leads, 1))
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())
    elif query.data == "admin_keywords":
        keywords = get_keywords()
        text = "🔑 Активных слов нет.\nНажми ➕ чтобы добавить." if not keywords else "🔑 <b>Активные кодовые слова:</b>\n\n" + "".join(f"• <b>{kw['word']}</b>\n  🎁 {kw['gift_link']}\n\n" for kw in keywords)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=admin_menu_keyboard())
    elif query.data == "admin_addkw":
        await query.edit_message_text("🔑 Напиши новое кодовое слово:\n(например: <code>контент2024</code>)\n\nИли /cancel для отмены", parse_mode="HTML")
        context.user_data["admin_state"] = "waiting_new_keyword"
    elif query.data == "admin_broadcast":
        stats = get_stats()
        await query.edit_message_text(f"📨 <b>Рассылка</b>\n\nВ базе: <b>{stats['total']}</b> человек\n\nНапиши текст сообщения.\nИли /cancel для отмены:", parse_mode="HTML")
        context.user_data["admin_state"] = "waiting_broadcast"

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    state = context.user_data.get("admin_state")
    if state == "waiting_new_keyword":
        context.user_data["new_keyword"] = update.message.text.strip().lower()
        context.user_data["admin_state"] = "waiting_new_gift"
        await update.message.reply_text(f"✅ Слово: <b>{context.user_data['new_keyword']}</b>\n\nТеперь напиши ссылку на подарок:", parse_mode="HTML")
    elif state == "waiting_new_gift":
        gift_link = update.message.text.strip()
        keyword = context.user_data.get("new_keyword", "")
        if add_keyword(keyword, gift_link):
            context.user_data["admin_state"] = None
            stats = get_stats()
            await update.message.reply_text(f"✅ <b>Добавлено!</b>\n\n🔑 Слово: <b>{keyword}</b>\n🎁 {gift_link}\n\n👑 Лидов: <b>{stats['total']}</b>",
                parse_mode="HTML", reply_markup=admin_menu_keyboard())
        else:
            await update.message.reply_text("❌ Ошибка. Попробуй ещё раз.")
    elif state == "waiting_broadcast":
        message_text = update.message.text.strip()
        leads = get_all_leads()
        if not leads:
            await update.message.reply_text("📭 База пуста.")
            context.user_data["admin_state"] = None
            return
        status = await update.message.reply_text(f"📤 Отправляю {len(leads)} людям...")
        sent = failed = 0
        for lead in leads:
            try:
                await context.bot.send_message(chat_id=lead["telegram_id"], text=message_text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO broadcasts (message, sent_at, sent_count) VALUES (%s, %s, %s)",
                    (message_text, datetime.now().strftime("%Y-%m-%d %H:%M"), sent))
        conn.commit()
        cur.close()
        conn.close()
        context.user_data["admin_state"] = None
        await status.edit_text(f"✅ <b>Рассылка готова!</b>\n📤 Отправлено: <b>{sent}</b>\n❌ Ошибок: <b>{failed}</b>",
            parse_mode="HTML", reply_markup=admin_menu_keyboard())

async def admin_delkeyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: <code>/delkeyword слово</code>", parse_mode="HTML")
        return
    deactivate_keyword(" ".join(args))
    await update.message.reply_text(f"✅ Слово <b>{' '.join(args)}</b> удалено.", parse_mode="HTML", reply_markup=admin_menu_keyboard())


async def admin_addlead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    # Usage: /addlead @username email keyword
    # Example: /addlead @Elmira_Begaliyeva Emika-86@mail.ru Тредс
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Использование:\n"
            "<code>/addlead @username email кодовое_слово</code>\n\n"
            "Пример:\n"
            "<code>/addlead @Elmira_Begaliyeva Emika-86@mail.ru Тредс</code>\n\n"
            "Если нет username — пиши id:\n"
            "<code>/addlead id123456 email@mail.ru Тредс</code>",
            parse_mode="HTML")
        return
    
    tg_ref = args[0]  # @username или id123456
    email = args[1]
    keyword = " ".join(args[2:])
    
    # Определяем telegram_id и username
    if tg_ref.startswith("@"):
        username = tg_ref[1:]
        telegram_id = 0  # неизвестен
        first_name = username
    elif tg_ref.startswith("id"):
        telegram_id = int(tg_ref[2:])
        username = ""
        first_name = f"id{telegram_id}"
    else:
        username = tg_ref
        telegram_id = 0
        first_name = username
    
    save_lead(telegram_id, username, first_name, email, keyword)
    stats = get_stats()
    await update.message.reply_text(
        f"✅ <b>Лид добавлен!</b>\n\n"
        f"👤 {first_name}\n"
        f"📧 {email}\n"
        f"🔑 {keyword}\n\n"
        f"👥 Всего в базе: <b>{stats['total']}</b>",
        parse_mode="HTML", reply_markup=admin_menu_keyboard())

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
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
    app.add_handler(user_conv)
    app.add_handler(CommandHandler("delkeyword", admin_delkeyword))
    app.add_handler(CommandHandler("addlead", admin_addlead))
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))
    logger.info("✅ Бот запущен — @ai_topkontentbot")
    app.run_polling()

if __name__ == "__main__":
    main()
