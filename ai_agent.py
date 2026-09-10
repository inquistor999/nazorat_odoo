import os
import json
import logging
from duckduckgo_search import DDGS
from odoo_client import OdooClient
import google.generativeai as genai
from odoo_tools import odoo_tools_list

def get_odoo_stats():
    """Odoo bazasidan umumiy statistikalarni olib beradi"""
    try:
        odoo = OdooClient()
        return odoo.get_general_stats()
    except Exception as e:
        return f"Odoo xatosi: {e}"

def search_internet(query: str):
    """Internetdan izlaydi"""
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return ""
        return "\n".join([f"- {r['title']}: {r['body']}" for r in results])
    except Exception as e:
        return ""

class AIAssistant:
    def __init__(self):
        self.memory_file = "memory.json"
        self.memory = self.load_memory()
        self.user_chats = {}
        
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            odoo_memory = (
                "Kompaniyaning Odoo bazasi haqida ma'lumotlar:\n"
                "- O'rnatilgan modullar soni: 271\n"
                "- Jami xodimlar/menejerlar (ichki foydalanuvchilar): 33 ta (jumladan: Behzod, Xasan, Samandar, Sunnat, Administrator, Sardor, Akmalxon, Sanjar, Ibrohim, Dilshod, Shahzod, Bahrom, Shoxrux, Oybek, Abdulaziz, Umid, Qaxramon, Shavkat, Mahmud, Jasur, Islom, Abduvohidjon, Nodir, Mirahmad, Ozodbek, Nodirjon, Saidvali, Zafar, Elmurod, Umar, Shuxrat)\n"
                "- Umumiy kontaktlar (mijozlar/hamkorlar) soni: 3662\n"
                "- Jami tovarlar/mahsulotlar soni: 1283\n"
                "- Oxirgi 30 kunlik savdo aylanmasi: 2198 ta buyurtma orqali jami 24,207,062,259.14 so'm (24.2 milliard so'm) savdo bo'lgan.\n"
                "Siz ushbu ma'lumotlarni yoddan bilasiz va so'ralganda shu ma'lumotlarga asoslanib javob berasiz."
            )
            system_instruction = f"Siz aqlli o'zbek tilidagi yordamchi botsiz. Qisqa va insoniy tilda javob bering. Mijozlar qarzi, tovar qoldig'i, yoki menejer mijozlarini bilish uchun asboblardan (tools) foydalaning.\n\n{odoo_memory}"
            
            self.model = genai.GenerativeModel(
                model_name='gemini-3.6-flash',
                tools=odoo_tools_list,
                system_instruction=system_instruction
            )
        else:
            self.model = None
        
    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
        
    def save_memory(self):
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Xotira saqlash xatosi: {e}")

    def find_in_memory(self, query):
        query_words = set(query.lower().split())
        best_match = None
        best_score = 0
        for stored_q, stored_a in self.memory.items():
            stored_words = set(stored_q.lower().split())
            score = len(query_words.intersection(stored_words)) / max(1, len(query_words.union(stored_words)))
            if score > 0.6 and score > best_score:
                best_score = score
                best_match = stored_a
        return best_match
        
    async def generate_response(self, prompt: str, user_id: int, image_path: str = None):
        if not self.model:
            return "⚠️ GEMINI_API_KEY topilmadi! Iltimos .env ga kalitni kiriting."
            
        import asyncio
        import PIL.Image
        import time
        import re
        def run_gemini():
            retries = 5
            for attempt in range(retries):
                try:
                    if user_id not in self.user_chats:
                        self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
                    chat = self.user_chats[user_id]
                    
                    content = [prompt]
                    if image_path:
                        try:
                            img = PIL.Image.open(image_path)
                            content.append(img)
                        except Exception as e:
                            logging.error(f"Rasm ochishda xato: {e}")
                    
                    response = chat.send_message(content)
                    return response.text
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg and attempt < retries - 1:
                        # Find "retry in 12.49s" pattern
                        match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_msg)
                        if match:
                            wait_time = float(match.group(1)) + 1.0
                        else:
                            wait_time = 15.0
                        time.sleep(wait_time)
                        continue
                    return f"Gemini Xatosi: {e}"
        return await asyncio.to_thread(run_gemini)

    async def get_response(self, text: str, user_id: int, image_path: str = None) -> str:
        # 1. Xotirani tekshiramiz
        if not image_path:
            mem_ans = self.find_in_memory(text)
            if mem_ans:
                return mem_ans
            
        context = ""
        # 2. Odoo statistikasimi?
        text_lower = text.lower()
        if 'odoo' in text_lower or 'ishchi' in text_lower or 'sotuv' in text_lower or 'statistika' in text_lower:
            odoo_data = get_odoo_stats()
            context += f"Odoo bazasidan hozir olingan ma'lumot:\n{odoo_data}\n"
            
        # 3. Internet qidiramiz
        if not context:
            web_data = search_internet(text)
            if web_data:
                context += f"Internetdan qidirilgan ma'lumot:\n{web_data}\n"
                
        # 4. LLM ga jo'natamiz
        if context:
            prompt = f"Foydalanuvchining savoli: {text}\nSenga yordam sifatida quyidagi ma'lumot topildi:\n{context}\nFaqat shu ma'lumot asosida yoki o'z biliming bilan javob tuz."
        else:
            prompt = text
            
        ans = await self.generate_response(prompt, user_id, image_path)
        
        # 5. Xotiraga saqlash
        if "Xatosi" not in ans and "GEMINI_API_KEY" not in ans and not image_path:
            self.memory[text] = ans
            self.save_memory()
            
        return ans

ai_assistant = AIAssistant()
