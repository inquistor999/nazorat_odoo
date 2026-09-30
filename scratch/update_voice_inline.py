import os

file_path = "ai_agent.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

old_voice_logic = """                    if voice_path:
                        try:
                            audio_file = genai.upload_file(path=voice_path)
                            response = chat.send_message([prompt, audio_file])
                            return response.text
                        except Exception as e:
                            logging.error(f"Ovozli fayl yuklashda xato: {e}")
                            return f"Ovozni tushunishda xato: {e}"
"""

new_voice_logic = """                    if voice_path:
                        try:
                            with open(voice_path, "rb") as f_voice:
                                audio_bytes = f_voice.read()
                            audio_part = {
                                "mime_type": "audio/ogg",
                                "data": audio_bytes
                            }
                            response = chat.send_message([prompt, audio_part])
                            return response.text
                        except Exception as e:
                            logging.error(f"Ovozli fayl yuklashda xato: {e}")
                            return f"Ovozni tushunishda xato: {e}"
"""
content = content.replace(old_voice_logic, new_voice_logic)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("ai_agent.py voice logic updated to use inline bytes!")
