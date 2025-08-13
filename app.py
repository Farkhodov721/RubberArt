from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
import asyncio
import os

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Salom! Bot ishga tushdi ✅")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
