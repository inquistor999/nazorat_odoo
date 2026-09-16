import os

file_path = "main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add allowed_users logic at the top of main.py
allowed_users_code = '''import json

ALLOWED_USERS_FILE = 'allowed_users.json'

def load_allowed_users():
    if os.path.exists(ALLOWED_USERS_FILE):
        try:
            with open(ALLOWED_USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_allowed_user(user_id):
    users = load_allowed_users()
    if user_id not in users:
        users.append(user_id)
        with open(ALLOWED_USERS_FILE, 'w') as f:
            json.dump(users, f)

def is_user_allowed(user_id):
    return user_id in load_allowed_users()
'''

# We need to insert this right after imports in main.py
import_str = "from background_jobs import run_monitoring_jobs\n"
content = content.replace(import_str, import_str + "\n" + allowed_users_code + "\n")


# Modify `start` function
old_start = '''async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "foydalanuvchi"
    welcome_text = f"👋 Salom {user_name}! Men yordamchi AI botman. Qanday savolingiz bor?"
    if update.message:
        await update.message.reply_text(welcome_text)
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome_text)
    return ConversationHandler.END'''

new_start = '''async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_user_allowed(user_id):
        return ConversationHandler.END

    user_name = update.effective_user.first_name if update.effective_user else "foydalanuvchi"
    welcome_text = f"👋 Salom {user_name}! Men yordamchi AI botman. Qanday savolingiz bor?"
    if update.message:
        await update.message.reply_text(welcome_text)
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome_text)
    return ConversationHandler.END'''

content = content.replace(old_start, new_start)


# Modify `handle_ai_or_atchot` function
old_handle = '''async def handle_ai_or_atchot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
        
    chat_type = update.message.chat.type
    if chat_type in ['group', 'supergroup']:
        return  # Guruhlarda umuman o'qimaydi va javob bermaydi, faqat tashiydi.
        
    user_name = update.effective_user.first_name or "Foydalanuvchi"
    text = update.message.text or update.message.caption or ""
    text = text.strip()'''

new_handle = '''async def handle_ai_or_atchot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
        
    chat_type = update.message.chat.type
    if chat_type in ['group', 'supergroup']:
        return  # Guruhlarda umuman o'qimaydi va javob bermaydi, faqat tashiydi.
        
    user_id = update.effective_user.id
    text = update.message.text or update.message.caption or ""
    text = text.strip()
    
    if text == "login:umar":
        save_allowed_user(user_id)
        await update.message.reply_text("✅ Tizimga kirdingiz! Endi botdan to'liq foydalanishingiz mumkin.")
        return ConversationHandler.END
        
    if not is_user_allowed(user_id):
        return ConversationHandler.END
        
    user_name = update.effective_user.first_name or "Foydalanuvchi"'''

content = content.replace(old_handle, new_handle)


# Send startup message to LOG_GROUP_ID
old_run_polling = '''    if render_url:
        port = int(os.environ.get('PORT', 10000))
        webhook_url = f"{render_url}/{config.TELEGRAM_BOT_TOKEN}"
        print(f"Render Webhook orqali ishga tushmoqda: {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=config.TELEGRAM_BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        print("Bot ishga tushdi (Polling)! Telegramdan /start yuboring.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)'''

new_run_polling = '''    async def send_startup_msg(app):
        grp_id = getattr(config, 'LOG_GROUP_ID', None) or getattr(config, 'ADMIN_CHAT_ID', None)
        if grp_id:
            try:
                await app.bot.send_message(chat_id=grp_id, text="✅ **Bot ishga tushdi va 24/7 monitoring faol!**", parse_mode='Markdown')
            except Exception as e:
                logging.error(f"Startup msg error: {e}")
                
    application.post_init = send_startup_msg

    if render_url:
        port = int(os.environ.get('PORT', 10000))
        webhook_url = f"{render_url}/{config.TELEGRAM_BOT_TOKEN}"
        print(f"Render Webhook orqali ishga tushmoqda: {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=config.TELEGRAM_BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        print("Bot ishga tushdi (Polling)! Telegramdan /start yuboring.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)'''

content = content.replace(old_run_polling, new_run_polling)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated main.py")
