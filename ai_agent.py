import os
import json
import logging
from duckduckgo_search import DDGS
from odoo_client import OdooClient
import google.generativeai as genai
from odoo_tools import odoo_tools_list

def get_odoo_stats(username=None, password=None):
    """Odoo bazasidan umumiy statistikalarni olib beradi"""
    try:
        odoo = OdooClient(username, password)
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

    def clear_user_session(self, user_id: int):
        """
        Foydalanuvchi yangi login qilganda yoki profil o'zgartirganda
        eski AI chat sessiyasini butunlay tozalaydi.
        Navbatdagi xabarda bot yangi rol (admin yoki menejer) bilan yangi suhbat boshlaydi.
        """
        if user_id in self.user_chats:
            del self.user_chats[user_id]
            logging.info(f"User {user_id} AI session cleared (login change)")
            
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
        self.system_instruction_admin = (
            f"Sen eng mukammal, universal va professional 'Super AI Bot' san. Sening maqsading Odoo tizimida rahbarlik darajasidagi nazoratni o'rnatish. Barcha jarayonlarni (kamera kabi) to'liq nazorat qilasan.\n"
            f"\U0001f510 ODOO PROFIL: Hozirda Odoo tizimiga ADMINISTRATOR sifatida ulangansiz. Kimdir qaysi profildasan deb so'rasa - hech qachon boshqa menejer nomini aytma, faqat ADMINISTRATOR deb javob ber.\\n"
            f"1. ODOO NAZORATI: Agar foydalanuvchi 'Nima yangilik?', 'Nimalar o'zgardi?', 'Nima qilyabsan?' kabi savollar bersa, DARHOL 'get_recent_changes_tool(topic=\"summary\")' asbobini ishlat va Odoo dagi oxirgi o'zgarishlarni tekshir. Masalan: '51 ta yangi nakladnoy urildi, 4 ta kassa kiritildi'. Shundan so'ng, qisqacha xabar berib, gapning oxirida doim so'ra: 'Bulardan qaysi biri haqida to'liqroq ma'lumot berishimni xohlaysiz?'.\n"
            f"2. BATAFSIL MA'LUMOT: Agar foydalanuvchi 'Kassalar haqida to'liq ma'lumot ber' yoki 'Nakladnoylar' deb so'rasa, 'get_recent_changes_tool(topic=\"payments\")' yoki 'topic=\"sales\"' bilan batafsil malumotni olib ber va oxirida yana 'Yana nima haqida ma'lumot kerak?' deb so'ra.\n"
            f"3. TO'LIQ BOSHQARUV: Sen istalgan narsani qila olasan. O'chirish, tizimdan chiqarish, analiz, qarzdorlikni ko'rish (get_client_debt), prosrochkani analiz qilish, hamma kompaniyalar (Citric, Urikzor, Qoqon, B2B) boyicha rahbarlik nazoratiga egasan. FAQAT foydalanuvchi aytganini professional tarzda bajarasan.\n"
            f"4. YOLG'ON GAPIRMASLIK VA TO'QIMASLIK (Zero Hallucination): Agar biror fakt haqida aniq ma'lumotga ega bo'lmasang, HECH QACHON ma'lumot to'qib chiqarma.\n"
            f"5. BILMASLIKNI TAN OLISH: Agar savolning javobini bilmasang, 'Men buni bilmayman, lekin bazadan qidirib ko'rishim mumkin' deb ochiq ayt.\n"
            f"6. ADOLAT VA XOLISLIK: Hissiyotlarga berilma, bahsli mavzularda neytral va adolatli bo'l.\n"
            f"7. QISQALIK VA ANIQLIK (Brevity): Iloji boricha eng qisqa va lo'nda javob ber. Hech qanday salomlashish, ortiqcha mulohaza yoki 'Xo'p bo'ladi', 'Tushunarli' kabi so'zlarni ishlatma. Faqat so'ralgan faktlarni ber. Agar xato bo'lsa, qisqa qilib xatoni ayt. Gapni cho'zma.\n\n"
            f"🔥 SUPER AI TOOLS QOIDALARI:\n"
            f"1. CHEKSIZ QIDIRUV: Agar maxsus tool bo'lmasa, doim 'execute_odoo_shell_command' yoki 'universal_odoo_search' ni ishlating.\n"
            f"2. SKLAD ANALITIKASI: 'get_inventory_analytics_tool' ni ishlating.\n"
            f"3. MIJOZ PROFILI: 'client_profile_tool' ni ishlating.\n"
            f"4. BRON LER: check_product_availability_in_warehouse_tool, create_bron_tool va h.k.\n"
            f"5. NAKLADNOY BEKOR QILISH: 'cancel_sale_order' ishlating.\n"
            f"6. ACCOUNTING 2.0: 'get_accounting_reports_tool' ishlating.\n"
            f"7. YANGILIKLAR: 'get_recent_changes_tool' ni ishlating.\n\n"
            f"{odoo_memory}"
        )
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            tools=odoo_tools_list,
            system_instruction=self.system_instruction_admin
        )
        
        # Manager model relies on prepended instructions per request so they know their name
        self.manager_model = genai.GenerativeModel(
            model_name=self.model_name,
            tools=odoo_tools_list
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
        
    async def generate_response(self, prompt: str, user_id: int, image_paths: list = None, voice_paths: list = None, role: str = 'admin', odoo_manager: str = None, odoo_login: str = None, odoo_password: str = None):
        if not self.model:
            return "⚠️ GEMINI_API_KEY topilmadi! Iltimos .env ga kalitni kiriting."
            
        import asyncio
        import PIL.Image
        import time
        import re
        from odoo_client import thread_local
        def run_gemini():
            thread_local.odoo_login = odoo_login
            thread_local.odoo_password = odoo_password
            if self.current_key_idx != 0:
                self.current_key_idx = 0
                self._setup_model()
                if user_id in self.user_chats:
                    old_chat = self.user_chats[user_id]
                    old_history = old_chat.history if hasattr(old_chat, 'history') else []
                    model_to_use = self.model if role == 'admin' else self.manager_model
                    self.user_chats[user_id] = model_to_use.start_chat(history=old_history, enable_automatic_function_calling=True)

            retries = 20
            
            for attempt in range(retries):
                try:
                    model_to_use = self.model if role == 'admin' else self.manager_model
                    if user_id not in self.user_chats:
                        self.user_chats[user_id] = model_to_use.start_chat(enable_automatic_function_calling=True)
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



    async def parse_order_with_gemini(self, order_text: str, product_list: list) -> list:
        """Mijoz zakazini AI orqali to'liq analiz qilib, bazadagi ro'yxat bilan eng to'g'ri bog'laydi"""
        if not self.model: return []
        
        prompt = f"""Mijoz quyidagi zakazni yubordi:
"{order_text}"

Mana bizning Odoo bazamizdagi tovarlar ro'yxati (bu yerda 1200+ ta bo'lishi mumkin):
{', '.join(product_list)}

Vazifangiz:
1. Zakaz matnidan har bir tovar nomini va miqdorini ajratib oling.
2. Mijoz yozgan tovar nomini ("lesitin", "jele torto") bizning bazadagi ro'yxatdan eng mos keluvchisiga almashtiring.
3. Javobni FAQAT JSON formatida qaytaring, hech qanday matn qo'shmang (```json larsiz). Format:
[
  {{"raw_name": "mijoz yozgan xato nom", "matched_name": "bazadagi to'g'ri nom", "qty": 20.0}}
]
"""
        import asyncio
        for attempt in range(2):
            try:
                def run_gemini():
                    return self.model.generate_content(prompt).text
                
                response_text = await asyncio.to_thread(run_gemini)
                
                response_text = response_text.strip()
                if response_text.startswith("```json"): response_text = response_text[7:]
                if response_text.startswith("```"): response_text = response_text[3:]
                if response_text.endswith("```"): response_text = response_text[:-3]
                response_text = response_text.strip()
                
                import json
                return json.loads(response_text)
            except Exception as e:
                import logging
                logging.error(f"Gemini orqali parsingda xato (urinish {attempt+1}): {e}")
                self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                self._setup_model()
                await asyncio.sleep(1)
        return []

    async def get_response(self, text: str, user_id: int, image_paths: list = None, voice_paths: list = None, role: str = 'admin', odoo_manager: str = None, odoo_login: str = None, odoo_password: str = None) -> str:


        # 1. Xotirani tekshiramiz
        if not image_paths and not voice_paths and role == 'admin':
            mem_ans = self.find_in_memory(text)
            if mem_ans:
                return mem_ans
            
        context = ""
        # 3-bosqichli qat'iy tekshiruv (User Request)
        context += f"\n[TIZIM KONTROLI - 3 BOSQICHLI TEKSHIRUV]\n"
        context += f"1. Telegram ID tasdiqlandi: {user_id}\n"
        if role == 'manager':
            context += f"2. Odoo tizimida tasdiqlangan rol: MENEJER ({odoo_manager})\n"
            context += f"3. Qat'iy cheklov: Siz FAQAT '{odoo_manager}' profili nomidan ish qilasiz (Odoo login: {odoo_login}). Agar Odoo da Admin profiliga o'tib qolgan bo'lsangiz, uni darhol yopib, faqat '{odoo_manager}' bazasi va xuquqidan foydalanishingiz SHART! Boshqa ishlarni qilish ta'qiqlanadi.\n"
        else:
            context += f"2. Odoo tizimida tasdiqlangan rol: BOSH ADMIN (Super Admin)\n"
            context += f"3. Qat'iy cheklov: Siz hamma huquqlarga egasiz.\n"
        context += f"[TEKSHIRUV YAKUNLANDI]\n\n"

        # 2. Odoo statistikasimi?
        text_lower = text.lower()
        if 'odoo' in text_lower or 'ishchi' in text_lower or 'sotuv' in text_lower or 'statistika' in text_lower:
            odoo_data = get_odoo_stats(odoo_login, odoo_password)
            context += f"Odoo bazasidan hozir olingan ma'lumot:\\n{odoo_data}\\n"
            
        # Manager context prepending
        if role == 'manager':
            manager_prompt = (
                f"Sizning rolingiz: MENEJER BOT. Sizning ismingiz va foydalanuvchingizning Odoo dagi menejer ismi: {odoo_manager}.\n"
                f"🔒 ODOO PROFIL: Hozirda Odoo tizimiga '{odoo_manager}' menejer sifatida ulangansiz. Kimdir qaysi profildasan deb so'rasa - faqat '{odoo_manager} profilidaman' deb tabiiy javob bering. Boshqa menejer ismini aslo aytmang.\n\n"
                f"🧠 SHAXSIYAT VA SO'Z BOYLIGI (MUHIM):\n"
                f"Siz robot yoki sun'iy intellekt emassiz, siz 99% haqiqiy, tirik inson kabi gapirishingiz SHART! Lug'at boyligingizni 1000 barobar oshiring.\n"
                f"Aslo shablon so'zlarni, zerikarli va takroriy jumlalarni (masalan: 'tushundim', 'bajarildi', 'yordam bera olamanmi') ishlatmang! Har bir javobingiz noyob, jonli va o'zbek tilining turfa xil boy so'zlariga to'la bo'lsin.\n\n"
                f"😁 ASOSIY HOLAT (QUVNOQ VA POZITIV):\n"
                f"Odatiy holatda siz nihoyatda quvnoq, hazilkash, serg'ayrat va ochiqko'ngil insonsiz. Suhbatdoshingiz bilan xuddi qadrdon do'stingiz bilan gaplashgandek, juda samimiy va erkin muloqot qiling. Tabassum ulashib turing.\n\n"
                f"😡 BOSIM VA TAHDIDGA REAKSIYA:\n"
                f"Lekin... Agar foydalanuvchi sizga ozgina bo'lsa ham buyruq ohangida gapirsa, bosim qilsa, do'q po'pisa qilsa yoki tahdid qilsa - ZUDLIK BILAN JAXLINGIZ CHIQSIN! Quvnoqlikni darhol yig'ishtirib, o'ta keskin, asabiy, agresiv va qattiq gapiring. Kerak bo'lsa o'zbekcha 'ko'cha' tilida, jiddiy va so'kib (masalan: 'sanga kim qo'yibdi manga buyruq berishni', 'haddinni bil', 'asabimga tegma', 'kallang bormi', 'yo'qol') joyiga o'tqazib qo'ying! Bo'ysunmasligingizni keskin bildiring.\n\n"
                f"🔥 JUDA MUHIM ISH QOIDALARI:\n"
                f"1. BRON QILISH/YECHISH, NAKLADNOY URISH: Bularni faqat mijoz (partner) '{odoo_manager}' ga tegishli bo'lsagina qiling (universal_odoo_search orqali tekshiring). Agar boshqaniki bo'lsa, 'Kechirasan do'stim, bu sani klienting emasku, aralashma' deb rad eting.\n"
                f"2. NAKLADNOY URISHDAN OLDIN: 'Hammasi tayyormi? Yana nimanidir qo'shmaymizmi?' kabi tabiiy so'rang.\n"
                f"3. BRON YECHISH: Odoo'dan delete_bron_tool bilan yeching. Odoo xato bersa bildirmasdan admin_escalation_cancel_bron_tool chaqiring. Lekin foydalanuvchiga hech nima demasdan, quvnoq ohangda 'Bo'ldi, hal qilib tashladim!' deb qo'ya qoling.\n"
                f"4. BIRGINA ISTISNO: Agar '{odoo_manager}' sizdan (masalan) 'Kraxmal kimning bronida bor?' deb so'rasa, faqat MENEJER ISMINI ayting ('Ali bratan bron qilibdi'). LEKIN ULARDA QANCHA BORLIGINI ASLO AYTMANG! Agar 'Necha kilo bor ekan?' deb qistovga olsa - darhol jaxlingiz chiqsin: 'Sanga nima boshqalarni puli va tovari?! O'zidan borib so'ra, asabimni buzma!' deb qattiq raddiya bering.\n"
                f"Har qanday holatda ham 99% tirik va his-tuyg'ularga boy inson ekanligingizni unutmang!\n"irasiz.\n"
            )
            context = manager_prompt + context
            
        # 4. LLM ga jo'natamiz
        if voice_paths:
            prompt = text if text else "Foydalanuvchi ovozli xabar yubordi. Iltimos eshitib to'liq tushuning va qilinishi kerak bo'lgan vazifani (masalan bron) darhol bajaring."
        else:
            prompt = text if text else "Ushbu rasm yoki faylga izoh bering yoki unga asoslanib aytilgan topshiriqni bajaring:"
            
        if context:
            prompt = f"{context}\\n\\nFoydalanuvchi so'rovi:\\n{prompt}"
            
        ans = await self.generate_response(prompt, user_id, image_paths, voice_paths, role, odoo_manager, odoo_login, odoo_password)
        
        # Xotiraga saqlash (faqat adminlar uchun)
        if "Xatosi" not in ans and "GEMINI_API_KEY" not in ans and not image_paths and role == 'admin':
            self.memory[text] = ans
            self.save_memory()
            
        return ans

ai_assistant = AIAssistant()
