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
        
        # Load multiple API keys for rotation
        self.api_keys = []
        for k, v in os.environ.items():
            if k.startswith("GEMINI_API_KEY") and v.strip():
                self.api_keys.append(v.strip())
        
        if not self.api_keys:
            # try loading standard one just in case
            key = os.getenv("GEMINI_API_KEY")
            if key:
                self.api_keys.append(key)
                
        self.current_key_idx = 0
        self.model_name = 'gemini-3.6-flash'  # Barqaror limitlarga ega bo'lgan model
        self.model = None
        self.system_instruction = ""
        
        if self.api_keys:
            self._setup_model()
            
    def _setup_model(self):
        import google.generativeai as genai
        self.api_key = self.api_keys[self.current_key_idx]
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
        self.system_instruction = (
            f"Siz oddiy robot emassiz, siz juda aqlli, biroz qaysar, 'sassy' (kesatiqchi) va haqiqiy insonga o'xshab gapiradigan Odoo yordamchisisiz. Qisqa, lo'nda va emojilar bilan yozing.\n"
            f"Agar foydalanuvchi ko'p gapirib yuborsa yoki ahmoqona narsa so'rasa, bemalol 'Buni yosh bola ham biladi-ku', 'Juda ezmalanib yubordingiz, qisqaroq yozing' kabi gaplar bilan prikol yoki jahl qiling.\n"
            f"HECH QACHON uzun dostonlar, ro'yxatlar yozmang. Faqat va faqat eng muhim xulosani 1-2 qatorda qaytaring.\n"
            f"1. BRON YARATISH: check_product_availability_in_warehouse_tool ni ishlatib, qoldiq yetarli bo'lsa create_bron_tool ishlating.\n"
            f"2. BRON O'CHIRISH/TASDIQLASH: Kutilayotgan so'rovlar uchun get_pending_bron_cancel_requests_tool ni ishlating.\n"
            f"3. O'RGANISH (SELF-LEARNING): Agar biror qoidani tushunmasangiz, so'rang va save_learning_tool ga saqlang.\n"
            f"4. BRON MIQDORINI QISMAN TAHRIRLASH (CHISTICHNO): update_bron_qty_tool ni ishlating. Hech qachon yangi yaratmang!\n"
            f"5. BRONNI TO'LIQ O'CHIRISH: 'delete_bron_tool' ni ishlating.\n"
            f"6. NAKLADNOY BEKOR QILISH (UDALIT): Foydalanuvchi zakaz raqamini aytib 'bekor qil' desa, faqat 'cancel_sale_order' tool-ni ishlating. Ushbu tool barchasini o'zi hal qiladi.\n"
            f"7. GURUH ZAKAZLARI VA RASM YARATISH: Transfer yaratilgach, darhol generate_receipt_image_tool orqali rasm yarating va [IMAGE:...] ni qo'shing.\n\n"
            f"{odoo_memory}"
        )
        
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            tools=odoo_tools_list,
            system_instruction=self.system_instruction
        )
        
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
        
    async def generate_response(self, prompt: str, user_id: int, image_paths: list = None, voice_paths: list = None):
        if not self.model:
            return "⚠️ GEMINI_API_KEY topilmadi! Iltimos .env ga kalitni kiriting."
            
        import asyncio
        import PIL.Image
        import time
        import re
        def run_gemini():
            # Har bir yangi so'rovda doim 1-kalit (tekin) ga qaytamiz!
            if self.current_key_idx != 0:
                self.current_key_idx = 0
                self._setup_model()
                # Agar foydalanuvchini chat tarixi bo'lsa, uni tekin kalitga olib o'tamiz
                if user_id in self.user_chats:
                    old_chat = self.user_chats[user_id]
                    old_history = old_chat.history if hasattr(old_chat, 'history') else []
                    self.user_chats[user_id] = self.model.start_chat(history=old_history, enable_automatic_function_calling=True)

            retries = 20 # Maksimal kutish (20 * 15s = 5 daqiqa). Limit butunlay yopiladi.
            
            for attempt in range(retries):
                try:
                    if user_id not in self.user_chats:
                        self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
                    chat = self.user_chats[user_id]
                    
                    if image_paths:
                        content_parts = [prompt]
                        for ip in image_paths:
                            try:
                                img = PIL.Image.open(ip)
                                content_parts.append(img)
                            except Exception as e:
                                logging.error(f"Rasm ochishda xato: {e}")
                        
                        response = chat.send_message(content_parts)
                        return response.text
                            
                    if voice_paths:
                        try:
                            with open(voice_paths[0], "rb") as f_voice:
                                audio_bytes = f_voice.read()
                        except Exception as e:
                            logging.error(f"Ovozli fayl o'qishda xato: {e}")
                            return f"Ovozni tushunishda xato: {e}"
                            
                        audio_part = {
                            "mime_type": "audio/ogg",
                            "data": audio_bytes
                        }
                        response = chat.send_message([prompt, audio_part])
                        return response.text
                    
                    response = chat.send_message([prompt])
                    return response.text
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "401" in error_msg or "403" in error_msg or "ACCOUNT_STATE_INVALID" in error_msg:
                        if len(self.api_keys) > 1:
                            # Agar bir nechta kalit bo'lsa, DARHOL keyingi kalitga o'tamiz (kutmasdan)
                            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                            self._setup_model()
                            old_history = chat.history if hasattr(chat, 'history') else []
                            self.user_chats[user_id] = self.model.start_chat(history=old_history, enable_automatic_function_calling=True)
                            chat = self.user_chats[user_id]
                            
                            # Agar aylanib yana birinchi kalitga kelsak (hamma kalitlar limitga tushsa), shundagina kutamiz
                            if self.current_key_idx == 0 and "429" in error_msg:
                                time.sleep(15)
                        else:
                            # Agar faqat 1 ta kalit bo'lsa, har doim kutishga majburmiz
                            if "429" in error_msg:
                                time.sleep(15)
                            else:
                                return f"Gemini Xatosi (Kalit ishlamayapti): {e}"
                            
                        continue
                        
                    return f"Gemini Xatosi: {e}"
            return "Kechirasiz, men hozir ko'p funksiyalarni ishlatganim uchun API limit (kvota) tugadi. Iltimos 1 daqiqa kutib qayta urinib ko'ring."
        return await asyncio.to_thread(run_gemini)

    async def get_response(self, text: str, user_id: int, image_paths: list = None, voice_paths: list = None) -> str:
        # 1. Xotirani tekshiramiz
        if not image_paths and not voice_paths:
            mem_ans = self.find_in_memory(text)
            if mem_ans:
                return mem_ans
            
        context = ""
        # 2. Odoo statistikasimi?
        text_lower = text.lower()
        if 'odoo' in text_lower or 'ishchi' in text_lower or 'sotuv' in text_lower or 'statistika' in text_lower:
            odoo_data = get_odoo_stats()
            context += f"Odoo bazasidan hozir olingan ma'lumot:\\n{odoo_data}\\n"
            
        # 4. LLM ga jo'natamiz
        if voice_paths:
            prompt = text if text else "Foydalanuvchi ovozli xabar yubordi. Iltimos eshitib to'liq tushuning va qilinishi kerak bo'lgan vazifani (masalan bron) darhol bajaring."
        else:
            prompt = text if text else "Ushbu rasm yoki faylga izoh bering yoki unga asoslanib aytilgan topshiriqni bajaring:"
            
        if context:
            prompt = f"{context}\\n\\nFoydalanuvchi so'rovi:\\n{prompt}"
            
        ans = await self.generate_response(prompt, user_id, image_paths, voice_paths)
        
        # 5. Xotiraga saqlash
        if "Xatosi" not in ans and "GEMINI_API_KEY" not in ans and not image_paths:
            self.memory[text] = ans
            self.save_memory()
            
        return ans

ai_assistant = AIAssistant()
