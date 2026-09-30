import os
import re

file_path = "ai_agent.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update get_response signature and prompt logic
old_def = "async def get_response(self, text: str, user_id: int, image_path: str = None) -> str:"
new_def = "async def get_response(self, text: str, user_id: int, image_path: str = None, voice_path: str = None) -> str:"
content = content.replace(old_def, new_def)

old_prompt_logic = """        if not image_path:
            mem_ans = self.find_in_memory(text)
            if mem_ans:
                return mem_ans
            
        context = ""
        # 2. Odoo statistikasimi?
        text_lower = text.lower()
        if 'odoo' in text_lower or 'ishchi' in text_lower or 'sotuv' in text_lower or 'statistika' in text_lower:
            odoo_data = get_odoo_stats()
            context += f"Odoo bazasidan hozir olingan ma'lumot:\\n{odoo_data}\\n"
            
        # 3. Internet qidiramiz (Hozircha o'chirilgan, chunki DDGS qotib qolyapti)
        # if not context and text:
        #     web_data = await asyncio.to_thread(search_web, text)
        #     context += f"Internetdan ma'lumot:\\n{web_data}\\n"
            
        prompt = text if text else "Ushbu rasm yoki faylga izoh bering yoki unga asoslanib aytilgan topshiriqni bajaring:"
        if context:
            prompt = f"{context}\\n\\nFoydalanuvchi so'rovi:\\n{prompt}"
"""
new_prompt_logic = """        if not image_path and not voice_path:
            mem_ans = self.find_in_memory(text)
            if mem_ans:
                return mem_ans
            
        context = ""
        text_lower = text.lower()
        if 'odoo' in text_lower or 'ishchi' in text_lower or 'sotuv' in text_lower or 'statistika' in text_lower:
            odoo_data = get_odoo_stats()
            context += f"Odoo bazasidan hozir olingan ma'lumot:\\n{odoo_data}\\n"
            
        if voice_path:
            prompt = text if text else "Foydalanuvchi ovozli xabar yubordi. Eshitib to'liq tushuning va aytilgan topshiriqni (masalan bron) bajaring."
        else:
            prompt = text if text else "Ushbu rasm yoki faylga izoh bering yoki unga asoslanib aytilgan topshiriqni bajaring:"
            
        if context:
            prompt = f"{context}\\n\\nFoydalanuvchi so'rovi:\\n{prompt}"
"""
content = content.replace(old_prompt_logic, new_prompt_logic)

# 2. Update run_gemini to handle voice and optimize retries
old_run_gemini = """        def run_gemini():
            retries = max(5, len(self.api_keys) * 2)
            
            for attempt in range(retries):
                try:
                    if user_id not in self.user_chats:
                        self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
                    chat = self.user_chats[user_id]
                    
                    if image_path:
                        try:
                            img = PIL.Image.open(image_path)
                            response = self.model.generate_content([prompt, img])
                            return response.text
                        except Exception as e:
                            logging.error(f"Rasm ochishda xato: {e}")
                            return f"Rasm tahlil qilishda xato: {e}"
                    
                    response = chat.send_message([prompt])
                    return response.text
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg:
                        # 429 Quota Exceeded xatosi
                        if len(self.api_keys) > 1:
                            # Agar bir nechta kalit bo'lsa, keyingisiga o'tamiz
                            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                            self._setup_model()
                            # Yangi modelda chatni qayta ochamiz
                            self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
                            chat = self.user_chats[user_id]
                            time.sleep(1) # Ozgina kutiladi
                            continue
                        else:
                            # Agar bitta kalit bo'lsa, kutamiz
                            if attempt < retries - 1:
                                match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_msg)
                                wait_time = float(match.group(1)) + 1.0 if match else 10.0
                                time.sleep(min(wait_time, 20.0)) # Maksimum 20 sek kutamiz
                                continue
                            else:
                                return f"Limit tugadi. Iltimos .env faylga yangi API kalit qo'shing: GEMINI_API_KEY_2=... xatosi: {error_msg}"
                    return f"Gemini Xatosi: {e}"
            return "Limit tugadi. Barcha kalitlarda (API keys) 429 xatosi yuz berdi yoki retries tugadi. Iltimos, keyinroq urinib ko'ring yoki yangi kalit qo'shing."
"""
new_run_gemini = """        def run_gemini():
            retries = max(6, len(self.api_keys) * 3) # Ko'proq urinish
            
            for attempt in range(retries):
                try:
                    if user_id not in self.user_chats:
                        self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
                    chat = self.user_chats[user_id]
                    
                    if image_path:
                        try:
                            img = PIL.Image.open(image_path)
                            response = self.model.generate_content([prompt, img])
                            return response.text
                        except Exception as e:
                            logging.error(f"Rasm ochishda xato: {e}")
                            return f"Rasm tahlil qilishda xato: {e}"
                            
                    if voice_path:
                        try:
                            audio_file = genai.upload_file(path=voice_path)
                            response = chat.send_message([prompt, audio_file])
                            return response.text
                        except Exception as e:
                            logging.error(f"Ovozli fayl yuklashda xato: {e}")
                            return f"Ovozni tushunishda xato: {e}"
                    
                    response = chat.send_message([prompt])
                    return response.text
                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg:
                        # Limit to'lsa, har safar 15 sekund kutamiz (RPM limit 15 ta bo'lgani uchun)
                        # Bu bot "Limit tugadi" demasligi uchun yordam beradi.
                        time.sleep(15) 
                        
                        if len(self.api_keys) > 1:
                            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                            self._setup_model()
                            self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
                            
                        continue
                        
                    return f"Gemini Xatosi: {e}"
            return "Kechirasiz, men hozir ko'p funksiyalarni ishlatganim uchun API limit (kvota) tugadi. Iltimos 1 daqiqa kutib qayta urinib ko'ring."
"""
content = content.replace(old_run_gemini, new_run_gemini)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("ai_agent.py updated for voice and smart retry!")
