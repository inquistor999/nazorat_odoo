import os

file_path = "main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find Application.builder()
old_builder = "application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).request(request).build()"

new_builder = '''    async def send_startup_msg(app):
        grp_id = getattr(config, 'LOG_GROUP_ID', None) or getattr(config, 'ADMIN_CHAT_ID', None)
        if grp_id:
            try:
                await app.bot.send_message(chat_id=grp_id, text="✅ **Bot ishga tushdi va 24/7 monitoring faol!**", parse_mode='Markdown')
            except Exception as e:
                logging.error(f"Startup msg error: {e}")
                
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).request(request).post_init(send_startup_msg).build()'''

content = content.replace(old_builder, new_builder)

old_post_init = '''    async def send_startup_msg(app):
        grp_id = getattr(config, 'LOG_GROUP_ID', None) or getattr(config, 'ADMIN_CHAT_ID', None)
        if grp_id:
            try:
                await app.bot.send_message(chat_id=grp_id, text="✅ **Bot ishga tushdi va 24/7 monitoring faol!**", parse_mode='Markdown')
            except Exception as e:
                logging.error(f"Startup msg error: {e}")
                
    application.post_init = send_startup_msg'''

content = content.replace(old_post_init, "")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("main.py updated!")
