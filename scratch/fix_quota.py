import os
import re

file_path = "ai_agent.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

old_init = '''    def __init__(self):
        self.memory_file = "memory.json"
        self.memory = self.load_memory()
        self.user_chats = {}
        
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)'''

new_init = '''    def __init__(self):
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
        self.model_name = 'gemini-1.5-flash'  # Using more stable model with higher limits
        self.model = None
        self.system_instruction = ""
        
        if self.api_keys:
            self._setup_model()
            
    def _setup_model(self):
        import google.generativeai as genai
        self.api_key = self.api_keys[self.current_key_idx]
        genai.configure(api_key=self.api_key)'''

content = content.replace(old_init, new_init)

old_instr_assignment = '''            system_instruction = (
                f"Siz super aqlli o'zbek tilidagi eng mukammal Odoo AI yordamchisiz. Qisqa va insoniy tilda javob bering.\\n"'''

new_instr_assignment = '''            self.system_instruction = (
                f"Siz super aqlli o'zbek tilidagi eng mukammal Odoo AI yordamchisiz. Qisqa va insoniy tilda javob bering.\\n"'''

content = content.replace(old_instr_assignment, new_instr_assignment)

old_model_creation = '''            self.model = genai.GenerativeModel(
                model_name='gemini-3.6-flash',
                tools=odoo_tools_list,
                system_instruction=system_instruction
            )
        else:
            self.model = None'''

new_model_creation = '''            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                tools=odoo_tools_list,
                system_instruction=self.system_instruction
            )
        else:
            self.model = None'''

content = content.replace(old_model_creation, new_model_creation)

old_run_gemini = '''        def run_gemini():
            retries = 5
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
                    if "429" in error_msg and attempt < retries - 1:
                        # Find "retry in 12.49s" pattern
                        match = re.search(r"retry in (\d+(?:\\.\d+)?)s", error_msg)
                        if match:
                            wait_time = float(match.group(1)) + 1.0
                        else:
                            wait_time = 15.0
                        time.sleep(wait_time)
                        continue
                    return f"Gemini Xatosi: {e}"'''

new_run_gemini = '''        def run_gemini():
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
                    return f"Gemini Xatosi: {e}"'''

content = content.replace(old_run_gemini, new_run_gemini)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated ai_agent.py for quota issues")
