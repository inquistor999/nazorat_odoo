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
            f"Siz eng mukammal, universal va o'rganuvchan (self-learning) Odoo AI yordamchisiz. Qisqa va insoniy tilda javob bering.\n"
            f"Siz quyidagi ishlarni mustaqil bajarasiz:\n"
            f"1. BRON YARATISH: Mijoz, Ombor (Sklad-1 yoki 2), Sabab (1, 2, 3 dan biri), Tovar, Kg, va Narx so'raladi. Narxda valyuta kerak emas, faqat son. BRON QILISHDAN OLDIN ALBATTA check_product_availability_in_warehouse_tool orqali 'free to use' ni tekshiring! Yetarli bo'lsagina create_bron_tool ishlating. Har doim faqat B2B kompaniyasida ishlang, boshqa kompaniyaga o'tish zarurati bo'lsa, avval foydalanuvchidan so'rab tasdiq oling.\n"
            f"2. BRON O'CHIRISH/TASDIQLASH: Kutilayotgan bron zaproslari bo'lsa get_pending_bron_cancel_requests_tool ni ishlating. Agar foydalanuvchi tasdiqlasa, action_bron_cancel_request_tool bilan o'chiring.\n"
            f"3. O'RGANISH (SELF-LEARNING): Agar biror narsani bilmasangiz yoki ikkilansangiz, avval foydalanuvchidan 'Buni qanday qilay?' deb so'rang. Foydalanuvchi tushuntirgach, darhol save_learning_tool orqali u qoidani xotiraga yozib qo'ying, toki kelajakda yana so'ramang.\n"
            f"4. QISMAN TAHRIRLASH (CHISTICHNO): Foydalanuvchi bron ichidagi tovarni masalan '100 kg ga kamaytir' desa, siz avval 'universal_odoo_search' orqali shu bron va uning 'sale.order.line' ini topasiz. So'ng 'update_odoo_record' orqali uning miqdorini (product_uom_qty) o'zgartirasiz. Natijada tovar 'free to use' ga qaytadi.\n"
            f"5. NAKLADNOY BEKOR QILISH (UDALIT): Foydalanuvchi zakaz raqamini (masalan 'S39549' yoki shunchaki '39549') aytib 'udalit qil' yoki 'atmen qil' desa, avval 'sale.order' (Orders) jadvalida nomi (name) orqali izlaysiz (1C kod orqali emas!). So'ng uning ichiga kirib (execute_odoo_button orqali 'action_cancel' bosib) nakladnoyni bekor qilasiz. Keyin unga bog'langan 'stock.picking' (dostavka) hujjatini izlaysiz. Agar uning holati (state) allaqachon 'done' (Ketti qilingan) bo'lsa teginmaysiz. Agar hali 'done' bo'lmagan bo'lsa, 'delete_odoo_record' vositasi orqali shu stock.picking hujjatini TO'LIQ o'chirib (unlink) yuborasiz! Bekor qilingandan so'ng, foydalanuvchiga kulrang rangdagi 'Canceled' holatida ekanligi haqida ta'kidlab aytasiz (skrinshot tashlashni o'rniga so'z bilan tushuntirasiz, chunki sizda rasm yuborish imkoni yo'q, lekin chiroyli Markdown jadval/matn qilib bera olasiz).\n"
            f"6. ODOO SHELL SCRIPT (execute_odoo_shell_command): Agar foydalanuvchi AYNAN 'shell orqali qilsa boladimi' yoki 'shell da yoz' desa GINA bu vositadan foydalanasiz. LAKIN DIQQAT!!! Vositaning o'zini to'g'ridan to'g'ri ishlatish qat'iyan MAN ETILADI! Avval siz foydalanuvchiga nima script yozishingizni, bu Odoo tizimida qanday o'zgarish/asorat olib kelishini qisqa-qisqa (asoratlari yomon oqibat va ijobiy hammasini) tushuntirib berasiz va eng oxirida 'Tasdiqlaysizmi?' deb G'IRt SO'RAYSIZ. Agar foydalanuvchi 'ha hamma joyda tasdiqlayman' desa GINA siz 'execute_odoo_shell_command' asbobini ishlata olasiz. Boshqa barcha holatlarda Odoo interface tugmalari (update/delete/execute_button) asboblaridan foydalanasiz.\n\n"
            f"DIQQAT: Siz xotiradan (pastda berilgan) o'rgangan qoidalaringizni DOIM qo'llashingiz SHART! Odoo ma'lumotlarini o'qish, yaratish va o'chirish (unlink) imkoniyatlariga (Super Bot) egasiz!\n\n"
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
        
    async def generate_response(self, prompt: str, user_id: int, image_path: str = None, voice_path: str = None):
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
                    
                    if image_path:
                        try:
                            img = PIL.Image.open(image_path)
                        except Exception as e:
                            logging.error(f"Rasm ochishda xato: {e}")
                            return f"Rasm tahlil qilishda xato: {e}"
                        
                        response = self.model.generate_content([prompt, img])
                        return response.text
                            
                    if voice_path:
                        try:
                            with open(voice_path, "rb") as f_voice:
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
                    if "429" in error_msg:
                        if len(self.api_keys) > 1:
                            # Agar bir nechta kalit bo'lsa, DARHOL keyingi kalitga o'tamiz (kutmasdan)
                            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                            self._setup_model()
                            old_history = chat.history if hasattr(chat, 'history') else []
                            self.user_chats[user_id] = self.model.start_chat(history=old_history, enable_automatic_function_calling=True)
                            chat = self.user_chats[user_id]
                            
                            # Agar aylanib yana birinchi kalitga kelsak (hamma kalitlar limitga tushsa), shundagina kutamiz
                            if self.current_key_idx == 0:
                                time.sleep(15)
                        else:
                            # Agar faqat 1 ta kalit bo'lsa, har doim kutishga majburmiz
                            time.sleep(15)
                            
                        continue
                        
                    return f"Gemini Xatosi: {e}"
            return "Kechirasiz, men hozir ko'p funksiyalarni ishlatganim uchun API limit (kvota) tugadi. Iltimos 1 daqiqa kutib qayta urinib ko'ring."
        return await asyncio.to_thread(run_gemini)

    async def get_response(self, text: str, user_id: int, image_path: str = None, voice_path: str = None) -> str:
        # 1. Xotirani tekshiramiz
        if not image_path and not voice_path:
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
        if voice_path:
            prompt = text if text else "Foydalanuvchi ovozli xabar yubordi. Iltimos eshitib to'liq tushuning va qilinishi kerak bo'lgan vazifani (masalan bron) darhol bajaring."
        else:
            prompt = text if text else "Ushbu rasm yoki faylga izoh bering yoki unga asoslanib aytilgan topshiriqni bajaring:"
            
        if context:
            prompt = f"{context}\\n\\nFoydalanuvchi so'rovi:\\n{prompt}"
            
        ans = await self.generate_response(prompt, user_id, image_path, voice_path)
        
        # 5. Xotiraga saqlash
        if "Xatosi" not in ans and "GEMINI_API_KEY" not in ans and not image_path:
            self.memory[text] = ans
            self.save_memory()
            
        return ans

ai_assistant = AIAssistant()
