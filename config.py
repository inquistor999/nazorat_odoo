import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USERNAME = os.getenv("ODOO_USERNAME")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD")

def get_tracked_product_names():
    try:
        with open('tracked_products.txt', 'r', encoding='utf-8') as f:
            # Fayldan barcha bo'sh bo'lmagan qatorlarni ro'yxat qilib olish
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []
