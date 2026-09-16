import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
data = {"contents": [{"parts": [{"text": "salom"}]}]}
response = requests.post(url, json=data)
print(response.status_code)
print(response.text)
