import os

file_path = "main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update handle_ai_or_atchot for voice
old_handle = """    else:
        await update.message.chat.send_action(action='typing')
        
        image_path = None
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            image_path = f"temp_image_{update.effective_user.id}.jpg"
            await file.download_to_drive(image_path)
        elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('image/'):
            doc = update.message.document
            file = await context.bot.get_file(doc.file_id)
            image_path = f"temp_image_{update.effective_user.id}.jpg"
            await file.download_to_drive(image_path)
            
        response = await ai_assistant.get_response(text, update.effective_user.id, image_path)
        
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
            
        await update.message.reply_text(response)
        
        # Botning va foydalanuvchining xabarini bitta qilib guruhga yuborish
        if config.LOG_GROUP_ID:
            try:
                log_text = f"👤 Foydalanuvchi: {user_name}\\n💬 Xabar: {user_msg_text}\\n\\n🤖 Bot javobi:\\n{response}"
                await context.bot.send_message(chat_id=config.LOG_GROUP_ID, text=log_text)
            except Exception as e:
                logging.error(f"Guruhga javob logini yuborishda xato: {e}")
                
        return ConversationHandler.END"""

new_handle = """    else:
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
content = content.replace(old_handle, new_handle)

# 2. Update MessageHandler filters
old_handler = "MessageHandler((filters.TEXT | filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND, handle_ai_or_atchot)"
new_handler = "MessageHandler((filters.TEXT | filters.PHOTO | filters.VOICE | filters.Document.IMAGE) & ~filters.COMMAND, handle_ai_or_atchot)"
content = content.replace(old_handler, new_handler)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("main.py updated!")
