import os
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, Update
from aiogram.filters import CommandStart

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

@router.message()
async def echo_handler(message: Message):
    await message.answer(f"Ты написал: {message.text}")

# =========================
# WEBHOOK LOGIC
# =========================
async def on_startup(app: web.Application):
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown(app: web.Application):
    logging.info("🛑 Shutdown...")
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
