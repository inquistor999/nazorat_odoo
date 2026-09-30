import os

file_path = "ai_agent.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the retry loop to preserve history when switching keys
old_retry_logic = """                        if len(self.api_keys) > 1:
                            # Agar bir nechta kalit bo'lsa, DARHOL keyingi kalitga o'tamiz (kutmasdan)
                            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                            self._setup_model()
                            self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)"""

new_retry_logic = """                        if len(self.api_keys) > 1:
                            # Agar bir nechta kalit bo'lsa, DARHOL keyingi kalitga o'tamiz (kutmasdan)
                            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                            self._setup_model()
                            old_history = chat.history if hasattr(chat, 'history') else []
                            self.user_chats[user_id] = self.model.start_chat(history=old_history, enable_automatic_function_calling=True)
                            chat = self.user_chats[user_id]"""

content = content.replace(old_retry_logic, new_retry_logic)

# 2. Add reset to index 0 at the start of run_gemini
old_run_gemini = """        def run_gemini():
            retries = 20 # Maksimal kutish (20 * 15s = 5 daqiqa). Limit butunlay yopiladi."""

new_run_gemini = """        def run_gemini():
            # Har bir yangi so'rovda doim 1-kalit (tekin) ga qaytamiz!
            if self.current_key_idx != 0:
                self.current_key_idx = 0
                self._setup_model()
                # Agar foydalanuvchini chat tarixi bo'lsa, uni tekin kalitga olib o'tamiz
                if user_id in self.user_chats:
                    old_chat = self.user_chats[user_id]
                    old_history = old_chat.history if hasattr(old_chat, 'history') else []
                    self.user_chats[user_id] = self.model.start_chat(history=old_history, enable_automatic_function_calling=True)

            retries = 20 # Maksimal kutish (20 * 15s = 5 daqiqa). Limit butunlay yopiladi."""

content = content.replace(old_run_gemini, new_run_gemini)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated ai_agent.py to preserve history and always fallback to free key!")
