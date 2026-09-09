import os
import json
import logging
from duckduckgo_search import DDGS
from odoo_client import OdooClient
import g4f

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
        # So'zlar mosligi orqali xotirani tekshirish
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
        
    async def generate_g4f_response(self, prompt: str):
        import asyncio
        def run_g4f():
            try:
                client = g4f.client.Client()
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Siz aqlli, insoniy tilda gapiruvchi o'zbek tilidagi yordamchi botsiz. Qisqa va aniq javob bering."},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content
            except Exception as e:
                # Fallback to another model or default if gpt-4o provider fails
                try:
                    response2 = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return response2.choices[0].message.content
                except Exception as e2:
                    return f"Miyada uzilish ro'y berdi (G4F Xatosi): Asosiy xato: {e}, Qo'shimcha xato: {e2}"
        return await asyncio.to_thread(run_g4f)

    async def get_response(self, text: str, user_id: int) -> str:
        # 1. Xotirani tekshiramiz
        mem_ans = self.find_in_memory(text)
        if mem_ans:
            return f"🧠 Xotiradan:\n{mem_ans}"
            
        context = ""
        # 2. Odoo statistikasimi?
        text_lower = text.lower()
        if 'odoo' in text_lower or 'ishchi' in text_lower or 'sotuv' in text_lower or 'statistika' in text_lower:
            odoo_data = get_odoo_stats()
            context += f"Odoo bazasidan hozir olingan ma'lumot:\n{odoo_data}\n"
            
        # 3. Internet qidiramiz agar Odoo bilan bog'liq bo'lmasa
        if not context:
            web_data = search_internet(text)
            if web_data:
                context += f"Internetdan qidirilgan ma'lumot:\n{web_data}\n"
                
        # 4. G4F ga jo'natamiz
        if context:
            prompt = f"Foydalanuvchining savoli: {text}\nSenga yordam sifatida quyidagi ma'lumot topildi:\n{context}\nFaqat shu ma'lumot asosida yoki o'z biliming bilan javob tuz."
        else:
            prompt = text
            
        ans = await self.generate_g4f_response(prompt)
        
        # 5. Xotiraga saqlash
        if "Xatosi" not in ans:
            self.memory[text] = ans
            self.save_memory()
            
        return ans

ai_assistant = AIAssistant()
