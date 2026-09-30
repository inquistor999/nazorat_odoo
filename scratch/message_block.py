import os
from dotenv import load_dotenv
import requests

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_ID = "996602944"
MESSAGE = "salom qaxramon tolov qilishingni kutmoqdaman !"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {
    "chat_id": USER_ID,
    "text": MESSAGE
}

response = requests.post(url, data=data)
print(response.json())
