import os
import re

main_path = "main.py"
ai_path = "ai_agent.py"

# --- UPDATE main.py ---
with open(main_path, "r", encoding="utf-8") as f:
    main_content = f.read()

# Add global buffers at the top
buffer_init = """import config
from odoo_client import OdooClient
import time
import asyncio

user_message_buffers = {}
user_timers = {}

async def process_user_buffer(user_id, chat_id, context, user_name):
    buffer = user_message_buffers.pop(user_id, None)
    if not buffer:
        return
        
    texts = buffer.get('texts', [])
    image_paths = buffer.get('image_paths', [])
    voice_paths = buffer.get('voice_paths', [])
    
    combined_text = "\\n".join(texts)
    
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        response = await ai_assistant.get_response(combined_text, user_id, image_paths, voice_paths)
        
        # Cleanup
        for img in image_paths:
            if os.path.exists(img): os.remove(img)
        for voice in voice_paths:
            if os.path.exists(voice): os.remove(voice)
            
        await context.bot.send_message(chat_id=chat_id, text=response)
        
        # Log logic
        if config.LOG_GROUP_ID:
            log_text = f"👤 Foydalanuvchi: {user_name}\\n💬 Xabarlar soni: {len(texts) + len(image_paths) + len(voice_paths)}\\n\\n🤖 Bot javobi:\\n{response}"
            await context.bot.send_message(chat_id=int(config.LOG_GROUP_ID), text=log_text)
            
    except Exception as e:
        import logging
        logging.error(f"Process buffer error: {e}")
"""

# Replace imports section
main_content = re.sub(r'import config\nfrom odoo_client import OdooClient', buffer_init, main_content, count=1)

# Replace handle_message logic
old_handle_msg = """    if text.lower() == 'atchot':
        return await show_company_selection(update, context)
    else:
        await update.message.chat.send_action(action='typing')
        
        image_path = None
        voice_path = None
        
        if update.message.voice:
            voice_file = update.message.voice
            file = await context.bot.get_file(voice_file.file_id)
            voice_path = f"temp_voice_{update.effective_user.id}.ogg"
            await file.download_to_drive(voice_path)
            user_msg_text = "🎤 Ovozli xabar yubordi."
        elif update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            image_path = f"temp_image_{update.effective_user.id}.jpg"
            await file.download_to_drive(image_path)
        elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('image/'):
            doc = update.message.document
            file = await context.bot.get_file(doc.file_id)
            image_path = f"temp_image_{update.effective_user.id}.jpg"
            await file.download_to_drive(image_path)
            
        response = await ai_assistant.get_response(text, update.effective_user.id, image_path, voice_path)
        
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        if voice_path and os.path.exists(voice_path):
            os.remove(voice_path)
            
        await update.message.reply_text(response)
        
        # Botning va foydalanuvchining xabarini bitta qilib guruhga yuborish
        if config.LOG_GROUP_ID:
            try:
                log_text = f"👤 Foydalanuvchi: {user_name}\\n💬 Xabar: {user_msg_text}\\n\\n🤖 Bot javobi:\\n{response}"
                # chat_id integer bo'lishi kerak, shuning uchun int ga o'tkazamiz
                await context.bot.send_message(chat_id=int(config.LOG_GROUP_ID), text=log_text)
            except Exception as e:
                logging.error(f"Guruhga javob logini yuborishda xato: {e}")
                
        return ConversationHandler.END"""

new_handle_msg = """    if text.lower() == 'atchot':
        return await show_company_selection(update, context)
    else:
        # Xabarlarni yig'ish mantiqi (Aggregation)
        if user_id not in user_message_buffers:
            user_message_buffers[user_id] = {'texts': [], 'image_paths': [], 'voice_paths': []}
            
        buffer = user_message_buffers[user_id]
        
        if text:
            buffer['texts'].append(text)
            
        # Fayllarni yuklab olish (noyob ismlar bilan)
        timestamp = int(time.time() * 1000)
        if update.message.voice:
            voice_file = update.message.voice
            file = await context.bot.get_file(voice_file.file_id)
            voice_path = f"temp_voice_{user_id}_{timestamp}.ogg"
            await file.download_to_drive(voice_path)
            buffer['voice_paths'].append(voice_path)
        elif update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            image_path = f"temp_image_{user_id}_{timestamp}.jpg"
            await file.download_to_drive(image_path)
            buffer['image_paths'].append(image_path)
        elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('image/'):
            doc = update.message.document
            file = await context.bot.get_file(doc.file_id)
            image_path = f"temp_image_{user_id}_{timestamp}.jpg"
            await file.download_to_drive(image_path)
            buffer['image_paths'].append(image_path)
            
        # Eski timerni bekor qilish
        if user_id in user_timers:
            user_timers[user_id].cancel()
            
        # Yangi 5 soniyalik timer boshlash
        loop = asyncio.get_event_loop()
        task = loop.create_task(
            asyncio.sleep(4)
        )
        task.add_done_callback(
            lambda t: asyncio.create_task(process_user_buffer(user_id, update.message.chat_id, context, user_name)) if not t.cancelled() else None
        )
        user_timers[user_id] = task
                
        return ConversationHandler.END"""

main_content = main_content.replace(old_handle_msg, new_handle_msg)

with open(main_path, "w", encoding="utf-8") as f:
    f.write(main_content)


# --- UPDATE ai_agent.py ---
with open(ai_path, "r", encoding="utf-8") as f:
    ai_content = f.read()

# Modify get_response signature and run_gemini logic
old_get_response = """    async def get_response(self, prompt: str, user_id: int, image_path: str = None, voice_path: str = None) -> str:
        # Har safar so'rov boshlanganda TEKIN (1-kalit) ga qaytarish
        if self.current_key_idx != 0:
            self.current_key_idx = 0
            self._setup_model()
            # Agar foydalanuvchini chat tarixi bo'lsa, uni tekin kalitga olib o'tamiz
            if user_id in self.user_chats:
                old_chat = self.user_chats[user_id]
                old_history = old_chat.history if hasattr(old_chat, 'history') else []
                self.user_chats[user_id] = self.model.start_chat(history=old_history, enable_automatic_function_calling=True)

        def run_gemini():
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
                            return f"Rasm xatosi: {e}"
                        response = chat.send_message([prompt, img])
                        return response.text
                    elif voice_path:
                        try:
                            with open(voice_path, 'rb') as f:
                                audio_bytes = f.read()
                            
                            audio_data = {
                                "mime_type": "audio/ogg",
                                "data": audio_bytes
                            }
                            # Send both text prompt (if any) and audio
                            contents = [audio_data]
                            if prompt:
                                contents.append(prompt)
                                
                            response = chat.send_message(contents)
                            return response.text
                        except Exception as e:
                            logging.error(f"Ovozli fayl bilan ishlashda xato: {e}")
                            return f"Ovoz xatosi: {e}"
                    else:
                        response = chat.send_message(prompt)
                        return response.text"""

new_get_response = """    async def get_response(self, prompt: str, user_id: int, image_paths: list = None, voice_paths: list = None) -> str:
        image_paths = image_paths or []
        voice_paths = voice_paths or []
        
        # Har safar so'rov boshlanganda TEKIN (1-kalit) ga qaytarish
        if self.current_key_idx != 0:
            self.current_key_idx = 0
            self._setup_model()
            # Agar foydalanuvchini chat tarixi bo'lsa, uni tekin kalitga olib o'tamiz
            if user_id in self.user_chats:
                old_chat = self.user_chats[user_id]
                old_history = old_chat.history if hasattr(old_chat, 'history') else []
                self.user_chats[user_id] = self.model.start_chat(history=old_history, enable_automatic_function_calling=True)

        def run_gemini():
            retries = 20 # Maksimal kutish (20 * 15s = 5 daqiqa). Limit butunlay yopiladi.
            
            for attempt in range(retries):
                try:
                    if user_id not in self.user_chats:
                        self.user_chats[user_id] = self.model.start_chat(enable_automatic_function_calling=True)
                    chat = self.user_chats[user_id]
                    
                    contents = []
                    
                    for img_path in image_paths:
                        try:
                            img = PIL.Image.open(img_path)
                            contents.append(img)
                        except Exception as e:
                            logging.error(f"Rasm ochishda xato: {e}")
                            
                    for v_path in voice_paths:
                        try:
                            with open(v_path, 'rb') as f:
                                audio_bytes = f.read()
                            contents.append({"mime_type": "audio/ogg", "data": audio_bytes})
                        except Exception as e:
                            logging.error(f"Ovozli fayl xatosi: {e}")
                            
                    if prompt:
                        contents.append(prompt)
                        
                    if not contents:
                        contents.append("(Bo'sh xabar yoki fayllar o'qilmadi)")
                        
                    response = chat.send_message(contents)
                    return response.text"""

ai_content = ai_content.replace(old_get_response, new_get_response)

# Overwrite get_response and generate_response signatures in ai_agent.py
ai_content = ai_content.replace("def get_response(self, prompt: str, user_id: int, image_path: str = None, voice_path: str = None)", "def get_response(self, prompt: str, user_id: int, image_paths: list = None, voice_paths: list = None)")
ai_content = ai_content.replace("async def generate_response(self, prompt: str, user_id: int, image_path: str = None, voice_path: str = None)", "async def generate_response(self, prompt: str, user_id: int, image_paths: list = None, voice_paths: list = None)")

with open(ai_path, "w", encoding="utf-8") as f:
    f.write(ai_content)

print("Super updates applied successfully to main.py and ai_agent.py!")
