import os
import logging
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, Update
from aiogram.filters import Command, CommandStart
from aiohttp import web

# =========================
# ENV / CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_PATH = "/webhook"

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN is not set")

if not RENDER_EXTERNAL_URL:
    raise RuntimeError("❌ RENDER_EXTERNAL_URL is not set")

WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

# =========================
# DB HELPERS
# =========================
def get_db():
    conn = sqlite3.connect("stars.db")
    cursor = conn.cursor()
    return conn, cursor


def init_db():
    conn, cursor = get_db()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stars (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        stars INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stars_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        stars INTEGER,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


# =========================
# BOT / DISPATCHER
# =========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# =========================
# HANDLERS
# =========================
@router.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("🤖 Бот запущен и работает через webhook!")


@router.message(Command("star"))
async def add_star(message: Message):
    if not message.reply_to_message:
        await message.answer("❗ Ответь на сообщение участника, чтобы выдать ⭐")
        return

    parts = message.text.split()
    try:
        amount = int(parts[1]) if len(parts) > 1 else 1
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗ Пример: /star 3")
        return

    user = message.reply_to_message.from_user
    now = datetime.utcnow().isoformat()

    conn, cursor = get_db()

    cursor.execute("SELECT stars FROM stars WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()

    if row:
        cursor.execute(
            "UPDATE stars SET stars = stars + ? WHERE user_id = ?",
            (amount, user.id)
        )
    else:
        cursor.execute(
            "INSERT INTO stars (user_id, username, stars) VALUES (?, ?, ?)",
            (user.id, user.username, amount)
        )

    cursor.execute(
        "INSERT INTO stars_log (user_id, username, stars, created_at) VALUES (?, ?, ?, ?)",
        (user.id, user.username, amount, now)
    )

    conn.commit()
    conn.close()

    await message.answer(
        f"⭐ {user.username or user.first_name} получил {amount} ⭐"
    )


@router.message(Command("me"))
async def my_stats(message: Message):
    conn, cursor = get_db()

    user_id = message.from_user.id
    cursor.execute("SELECT stars FROM stars WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        await message.answer("У тебя пока нет ⭐")
        conn.close()
        return

    user_stars = row[0]

    cursor.execute("SELECT user_id FROM stars ORDER BY stars DESC")
    users = cursor.fetchall()

    place = [u[0] for u in users].index(user_id) + 1
    total = len(users)

    conn.close()

    await message.answer(
        f"👤 Твоя статистика:\n\n"
        f"⭐ Звёзды: {user_stars}\n"
        f"🏆 Место в рейтинге: {place} из {total}"
    )


@router.message(Command("top_week"))
async def top_week(message: Message):
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()

    conn, cursor = get_db()
    cursor.execute("""
        SELECT username, SUM(stars)
        FROM stars_log
        WHERE created_at >= ?
        GROUP BY user_id
        ORDER BY SUM(stars) DESC
        LIMIT 10
    """, (since,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("Пока нет данных за неделю")
        return

    text = "🏆 ТОП за неделю:\n\n"
    for i, (username, stars) in enumerate(rows, 1):
        text += f"{i}. {username or 'Без имени'} — ⭐ {stars}\n"

    await message.answer(text)


@router.message(Command("top_month"))
async def top_month(message: Message):
    since = (datetime.utcnow() - timedelta(days=30)).isoformat()

    conn, cursor = get_db()
    cursor.execute("""
        SELECT username, SUM(stars)
        FROM stars_log
        WHERE created_at >= ?
        GROUP BY user_id
        ORDER BY SUM(stars) DESC
        LIMIT 10
    """, (since,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.answer("Пока нет данных за месяц")
        return

    text = "🏆 ТОП за месяц:\n\n"
    for i, (username, stars) in enumerate(rows, 1):
        text += f"{i}. {username or 'Без имени'} — ⭐ {stars}\n"

    await message.answer(text)


# =========================
# WEBHOOK
# =========================
async def on_startup(app: web.Application):
    init_db()
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")


async def on_shutdown(app: web.Application):
    logging.info("🛑 Shutdown")
    await bot.delete_webhook()
    await bot.session.close()


async def telegram_webhook(request: web.Request):
    update = Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return web.Response(text="ok")


# =========================
# APP
# =========================
def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, telegram_webhook)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, port=PORT)


if __name__ == "__main__":
    main()
