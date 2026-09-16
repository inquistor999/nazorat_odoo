import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

for model in ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-flash-lite-latest", "gemini-pro-latest"]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    data = {"contents": [{"parts": [{"text": "salom"}]}]}
    response = requests.post(url, json=data)
    print(f"Model: {model} -> Status: {response.status_code}")
