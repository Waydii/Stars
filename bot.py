
import asyncio
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CHAT_ID = -5136406172

# ---------- БАЗА ДАННЫХ ----------
conn = sqlite3.connect("stars.db")
cursor = conn.cursor()

# общий рейтинг
cursor.execute("""
CREATE TABLE IF NOT EXISTS stars (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    stars INTEGER DEFAULT 0
)
""")

# история начислений
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


# ---------- КОМАНДЫ ----------

@dp.message(Command("star"))
async def add_star(message: types.Message):
    if not message.reply_to_message:
        await message.answer("❗ Ответь на сообщение участника, чтобы выдать звёзды")
        return

    # количество звёзд
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

    # обновляем общий рейтинг
    cursor.execute(
        "SELECT stars FROM stars WHERE user_id = ?",
        (user.id,)
    )
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

    # пишем историю
    cursor.execute(
        "INSERT INTO stars_log (user_id, username, stars, created_at) VALUES (?, ?, ?, ?)",
        (user.id, user.username, amount, now)
    )

    conn.commit()

    await message.answer(
        f"⭐ {user.username or user.first_name} получил {amount} ⭐"
    )


@dp.message(Command("me"))
async def my_stats(message: types.Message):
    user_id = message.from_user.id

    cursor.execute(
        "SELECT stars FROM stars WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()

    if not row:
        await message.answer("У тебя пока нет ⭐")
        return

    user_stars = row[0]

    cursor.execute(
        "SELECT user_id FROM stars ORDER BY stars DESC"
    )
    users = cursor.fetchall()

    place = [u[0] for u in users].index(user_id) + 1
    total = len(users)

    await message.answer(
        f"👤 Твоя статистика:\n\n"
        f"⭐ Звёзды: {user_stars}\n"
        f"🏆 Место в рейтинге: {place} из {total}"
    )


@dp.message(Command("top_week"))
async def top_week(message: types.Message):
    since = (datetime.utcnow() - timedelta(days=7)).isoformat()

    cursor.execute(
        """
        SELECT username, SUM(stars)
        FROM stars_log
        WHERE created_at >= ?
        GROUP BY user_id
        ORDER BY SUM(stars) DESC
        LIMIT 10
        """,
        (since,)
    )
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Пока нет данных за неделю")
        return

    text = "🏆 ТОП за неделю:\n\n"
    for i, (username, stars) in enumerate(rows, 1):
        text += f"{i}. {username or 'Без имени'} — ⭐ {stars}\n"

    await message.answer(text)


@dp.message(Command("top_month"))
async def top_month(message: types.Message):
    since = (datetime.utcnow() - timedelta(days=30)).isoformat()

    cursor.execute(
        """
        SELECT username, SUM(stars)
        FROM stars_log
        WHERE created_at >= ?
        GROUP BY user_id
        ORDER BY SUM(stars) DESC
        LIMIT 10
        """,
        (since,)
    )
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Пока нет данных за месяц")
        return

    text = "🏆 ТОП за месяц:\n\n"
    for i, (username, stars) in enumerate(rows, 1):
        text += f"{i}. {username or 'Без имени'} — ⭐ {stars}\n"

    await message.answer(text)


@dp.message(Command("chat_id"))
async def chat_id_cmd(message: types.Message):
    await message.answer(f"chat_id: {message.chat.id}")


# ---------- АВТОПОСТ ----------

async def autopost_top(bot: Bot, chat_id: int):
    while True:
        now = datetime.now()

        if now.weekday() == 6 and now.hour == 12:
            await bot.send_message(chat_id, "📊 Итоги недели — напиши /top_week")

        tomorrow = now + timedelta(days=1)
        if tomorrow.day == 1 and now.hour == 12:
            await bot.send_message(chat_id, "📊 Итоги месяца — напиши /top_month")

        await asyncio.sleep(3600)


# ---------- ЗАПУСК ----------

async def main():
    asyncio.create_task(autopost_top(bot, CHAT_ID))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
