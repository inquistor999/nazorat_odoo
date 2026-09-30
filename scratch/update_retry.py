import os

file_path = "ai_agent.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

old_retry_logic = """                    if "429" in error_msg:
                        # Limit to'lsa, har safar 15 sekund kutamiz (RPM limit 15 ta bo'lgani uchun)
                        # Bu bot "Limit tugadi" demasligi uchun yordam beradi.
                        time.sleep(15) 
                        
                        if len(self.api_keys) > 1:
                            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                            self._setup_model()
                            self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
                            
                        continue"""

new_retry_logic = """                    if "429" in error_msg:
                        if len(self.api_keys) > 1:
                            # Agar bir nechta kalit bo'lsa, DARHOL keyingi kalitga o'tamiz (kutmasdan)
                            self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                            self._setup_model()
                            self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
                            
                            # Agar aylanib yana birinchi kalitga kelsak (hamma kalitlar limitga tushsa), shundagina kutamiz
                            if self.current_key_idx == 0:
                                time.sleep(15)
                        else:
                            # Agar faqat 1 ta kalit bo'lsa, har doim kutishga majburmiz
                            time.sleep(15)
                            
                        continue"""
content = content.replace(old_retry_logic, new_retry_logic)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated ai_agent.py for instant fallback to second key!")
