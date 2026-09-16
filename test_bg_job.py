import asyncio
import os
from dotenv import load_dotenv
import logging
from background_jobs import run_monitoring_jobs

logging.basicConfig(level=logging.INFO)

class DummyContext:
    class DummyBot:
        async def send_message(self, chat_id, text, parse_mode=None):
            print(f"BOT SENDING TO {chat_id}: {text}")
    bot = DummyBot()

async def test_job():
    load_dotenv()
    context = DummyContext()
    await run_monitoring_jobs(context)

if __name__ == "__main__":
    asyncio.run(test_job())
