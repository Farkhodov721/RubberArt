import asyncio
from aiohttp import web
import os
from aiogram import Bot, Dispatcher, types

import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

# 📂 Load .env variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing! Check your .env file.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Example handler — you can import your real handlers here instead
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.reply("Hello! Bot is running.")

# Web server handler for uptime monitoring
async def handle(request):
    return web.Response(text="OK")

async def on_startup(app):
    # Start aiogram polling in background
    asyncio.create_task(dp.start_polling())

app = web.Application()
app.router.add_get('/', handle)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    web.run_app(app, host='0.0.0.0', port=int(os.getenv("PORT", 8080)))
