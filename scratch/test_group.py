import asyncio
import os
from telegram import Bot
from dotenv import load_dotenv

async def test_send():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("LOG_GROUP_ID")
    if not chat_id:
        print("LOG_GROUP_ID not found in .env")
        return
        
    bot = Bot(token)
    try:
        await bot.send_message(chat_id=chat_id, text="Bu test xabar. Agar buni o'qiyotgan bo'lsangiz, bot guruhga yozishga ruxsati bor!")
        print("Xabar muvaffaqiyatli yuborildi!")
    except Exception as e:
        print(f"Xatolik: {e}")

if __name__ == "__main__":
    asyncio.run(test_send())
