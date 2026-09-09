import os
import google.generativeai as genai
from duckduckgo_search import DDGS
from odoo_client import OdooClient
import logging

def get_odoo_stats():
    """Odoo bazasidan umumiy statistikalarni (ishchilar soni, bugungi savdo va hk) olib beradi"""
    try:
        odoo = OdooClient()
        return odoo.get_general_stats()
    except Exception as e:
        return f"Odoo bazasiga ulanishda xato: {e}"

def search_internet(query: str):
    """Internetdan (Google/DuckDuckGo) ixtiyoriy ma'lumotni izlaydi"""
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "Hech narsa topilmadi."
        return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except Exception as e:
        return f"Internetdan qidirishda xato: {e}"

class AIAssistant:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.system_instruction = (
                "Siz Odoo ERP tizimi uchun yaratilgan yordamchi AI botsiz. "
                "Foydalanuvchilar bilan insoniy, muloyim, qisqa va lo'nda tilda gaplashing. "
                "Kerak bo'lsa Odoo statistikasidan yoki internetdan olingan ma'lumotlardan foydalaning."
            )
            self.model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                tools=[get_odoo_stats, search_internet],
                system_instruction=self.system_instruction
            )
            self.chats = {}
        else:
            self.model = None

    def _get_chat(self, user_id):
        if user_id not in self.chats:
            self.chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
        return self.chats[user_id]

    async def get_response(self, text: str, user_id: int) -> str:
        if not self.model:
            return "⚠️ AI rejimi ishlamayapti, sababi GEMINI_API_KEY `.env` faylida kiritilmagan.\nIltimos admin bilan bog'laning."
            
        try:
            import asyncio
            chat = self._get_chat(user_id)
            response = await asyncio.to_thread(chat.send_message, text)
            return response.text
        except Exception as e:
            logging.error(f"AI Error: {e}")
            return "Kechirasiz, hozir men bu savolga javob bera olmayman. Tizimda xatolik yuz berdi."

ai_assistant = AIAssistant()
