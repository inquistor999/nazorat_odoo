import asyncio
import logging
from telegram.ext import ContextTypes

async def process_next_order_in_queue(context: ContextTypes.DEFAULT_TYPE):
    if 'order_queue' not in context.bot_data:
        context.bot_data['order_queue'] = []
        
    if context.bot_data.get('is_wizard_busy', False):
        return
        
    if not context.bot_data['order_queue']:
        return
        
    # Queue-da zakaz bor bo'lsa va bot bo'sh bo'lsa, navbatdagisini boshlaymiz
    context.bot_data['is_wizard_busy'] = True
    next_order = context.bot_data['order_queue'].pop(0)
    
    update = next_order['update']
    order_data = next_order['order_data']
    msg_id = next_order['msg_id']
    chat_id = next_order['chat_id']
    order_text = next_order['order_text']
    
    import group_order_wizard
    
    try:
        # User-larga xabar berish (agar kutgan bo'lsa)
        user_id = update.effective_user.id
        await context.bot.send_message(chat_id=user_id, text=f"📥 Navbatdagi zakaz ishlanmoqda... (Guruh ID: {chat_id}, SMS ID: {msg_id})")
        
        await group_order_wizard.start_group_order_wizard(update, context, order_data, msg_id, chat_id, order_text)
    except Exception as e:
        logging.error(f"Queue order processing error: {e}")
        context.bot_data['is_wizard_busy'] = False
        # Xato bo'lsa keyingisiga o'tib ketamiz
        asyncio.create_task(process_next_order_in_queue(context))

async def add_order_to_queue(update, context, order_data, msg_id, chat_id, order_text):
    if 'order_queue' not in context.bot_data:
        context.bot_data['order_queue'] = []
        
    context.bot_data['order_queue'].append({
        'update': update,
        'order_data': order_data,
        'msg_id': msg_id,
        'chat_id': chat_id,
        'order_text': order_text
    })
    
    q_len = len(context.bot_data['order_queue'])
    if context.bot_data.get('is_wizard_busy', False):
        user_id = update.effective_user.id
        await context.bot.send_message(chat_id=user_id, text=f"⏳ Yangi zakaz navbatga qo'shildi. Oldindagi zakazlar soni: {q_len}. Iltimos oldingi zakazni tasdiqlang yoki bekor qiling...")
        
    # Process
    await process_next_order_in_queue(context)

def release_wizard(context: ContextTypes.DEFAULT_TYPE):
    context.bot_data['is_wizard_busy'] = False
    asyncio.create_task(process_next_order_in_queue(context))
