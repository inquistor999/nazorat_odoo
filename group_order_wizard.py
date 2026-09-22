import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from odoo_client import OdooClient
from image_generator import generate_receipt_image

# States for the wizard
(
    SELECTING_PRODUCT_VARIANT,
    MANAGING_SHORTAGE,
    SELECTING_WAREHOUSE_MODE,
    SELECTING_WAREHOUSE_FOR_ITEM,
    CONFIRMING_ORDER,
) = range(5)

async def start_group_order_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE, order_data: dict, original_message_id: int, group_id: int, full_text: str = ""):
    """
    Triggered from main.py when a group order is detected.
    """
    admin_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not admin_chat_id:
        return

    from datetime import datetime
    today = datetime.now().strftime("%d.%m.%Y")
    
    # Avval to'liq matnni tashlaymiz
    initial_text = f"Zakaz : {today}\n{full_text}"
    await context.bot.send_message(chat_id=admin_chat_id, text=initial_text)

    context.user_data['wizard_order'] = order_data
    context.user_data['wizard_msg_id'] = original_message_id
    context.user_data['wizard_group_id'] = group_id
    context.user_data['wizard_current_item_idx'] = 0
    context.user_data['wizard_search_offset'] = 0

    await process_next_product(context.bot, admin_chat_id, context)

async def process_next_product(bot, chat_id, context, edit_message_id=None):
    order = context.user_data['wizard_order']
    idx = context.user_data['wizard_current_item_idx']
    offset = context.user_data.get('wizard_search_offset', 0)
    
    if idx >= len(order['items']):
        return await check_stock_for_order(bot, chat_id, context)
        
    item = order['items'][idx]
    from odoo_client import OdooClient
    
    keyboard = []
    
    try:
        client = OdooClient()
        words = item['raw_name'].split()
        domain = []
        for w in words:
            if len(w) >= 3:
                domain.append(('name', 'ilike', w))
                
        if not domain:
            domain = [('name', 'ilike', item['raw_name'])]
            
        products = client.models.execute_kw(client.db, client.uid, client.password, 
            'product.product', 'search_read', 
            [domain], 
            {'fields': ['id', 'name'], 'limit': 4, 'offset': offset})
            
        if products and isinstance(products, list):
            for p in products:
                name = p.get('name', 'Nomsiz')
                display_name = name[:40] + '...' if len(name) > 40 else name
                keyboard.append([InlineKeyboardButton(display_name, callback_data=f"prod_{name[:20]}")])
            
            if len(products) == 4:
                keyboard.append([InlineKeyboardButton("🔄 Yana variantlar (Next)", callback_data="prod_next_page")])
        else:
            if offset == 0:
                keyboard.append([InlineKeyboardButton("Variant topilmadi", callback_data="prod_notfound")])
    except Exception as e:
        keyboard.append([InlineKeyboardButton("Variant topilmadi (Xato)", callback_data="prod_error")])
        
    keyboard.append([InlineKeyboardButton("✏️ Qo'lda yozish (Manual)", callback_data="prod_notfound")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"{idx + 1}. zakaz : {item['raw_name']}\nOdoo dan to'g'ri nomni tanlang:"
    
    if edit_message_id:
        await bot.edit_message_text(chat_id=chat_id, message_id=edit_message_id, text=text, reply_markup=reply_markup)
    else:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

async def handle_product_variant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "prod_next_page":
        context.user_data['wizard_search_offset'] = context.user_data.get('wizard_search_offset', 0) + 4
        await process_next_product(context.bot, update.effective_chat.id, context, edit_message_id=query.message.message_id)
        return
        
    if query.data in ["prod_notfound", "prod_error"]:
        context.user_data['wizard_awaiting_manual_item_idx'] = context.user_data['wizard_current_item_idx']
        await query.message.edit_text("🔍 Tovar Odoo'dan topilmadi yoki kerakli variant yo'q.\nIltimos, Odoo dagi to'g'ri nomini chatga yozib yuboring:")
        return
        
    order = context.user_data['wizard_order']
    idx = context.user_data['wizard_current_item_idx']
    
    # query.data ichida 'prod_NOM' qismi bor. Lekin biz asl tugmadagi textni (yoki p['name'] ni) yozishimiz kerak.
    # Eng yaxshisi query.message dagi tugmalardan topish yoki shunchaki query.data dan foydalanish (faqat u 20 ta harfgacha kesilgan)
    # Ammo hozircha oddiy saqlaymiz:
    
    # Asl nomni tugmalar orasidan qidiramiz
    selected_name = "Nomsiz"
    for row in query.message.reply_markup.inline_keyboard:
        for btn in row:
            if btn.callback_data == query.data:
                selected_name = btn.text
                
    order['items'][idx]['matched_name'] = selected_name
    context.user_data['wizard_current_item_idx'] += 1
    context.user_data['wizard_search_offset'] = 0
    await process_next_product(context.bot, update.effective_chat.id, context)

async def check_stock_for_order(bot, chat_id, context):
    keyboard = [
        [InlineKeyboardButton("🏢 Bitta Sklad", callback_data="mode_single")],
        [InlineKeyboardButton("🔀 Aralash Sklad", callback_data="mode_mixed")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await bot.send_message(
        chat_id=chat_id, 
        text="✅ Barcha tovarlar aniqlandi va erkin qoldiq yetarli.\nSkladni tanlang:",
        reply_markup=reply_markup
    )

async def handle_warehouse_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "mode_single":
        keyboard = [
            [InlineKeyboardButton("Sklad - 1", callback_data="wh_single_1")],
            [InlineKeyboardButton("Sklad - 2", callback_data="wh_single_2")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Qaysi skladdan?", reply_markup=reply_markup)
        
    elif query.data.startswith("wh_single_"):
        wh = query.data.split('_')[-1]
        order = context.user_data['wizard_order']
        for item in order['items']:
            item['warehouse'] = f"Sklad - {wh}"
        await finalize_order(context.bot, update.effective_chat.id, context)
        
    elif query.data == "mode_mixed":
        context.user_data['wizard_wh_idx'] = 0
        await ask_warehouse_for_item(context.bot, update.effective_chat.id, context)

async def ask_warehouse_for_item(bot, chat_id, context):
    order = context.user_data['wizard_order']
    idx = context.user_data['wizard_wh_idx']
    
    if idx >= len(order['items']):
        return await finalize_order(bot, chat_id, context)
        
    item = order['items'][idx]
    keyboard = [
        [InlineKeyboardButton("Sklad - 1", callback_data=f"wh_mixed_1")],
        [InlineKeyboardButton("Sklad - 2", callback_data=f"wh_mixed_2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await bot.send_message(
        chat_id=chat_id, 
        text=f"📦 {item['raw_name']} ({item['qty']} kg) qaysi skladdan?",
        reply_markup=reply_markup
    )

async def handle_mixed_warehouse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    wh = query.data.split('_')[-1]
    order = context.user_data['wizard_order']
    idx = context.user_data['wizard_wh_idx']
    order['items'][idx]['warehouse'] = f"Sklad - {wh}"
    
    context.user_data['wizard_wh_idx'] += 1
    await ask_warehouse_for_item(context.bot, update.effective_chat.id, context)



async def finalize_order(bot, chat_id, context):
    order = context.user_data['wizard_order']
    
    wh_1_items = [i for i in order['items'] if i.get('warehouse') == 'Sklad - 1']
    wh_2_items = [i for i in order['items'] if i.get('warehouse') == 'Sklad - 2']
    
    from image_generator import generate_receipt_image
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash (Xa)", callback_data="wizard_confirm")],
        [InlineKeyboardButton("❌ Bekor qilish (Yo'q)", callback_data="wizard_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await bot.send_message(chat_id=chat_id, text="Tayyorlanayotgan chek rasmi (Preview):")
    
    if wh_1_items:
        img1 = generate_receipt_image(wh_1_items, "Sklad - 1", "O'rikzor")
        with open(img1, 'rb') as f:
            await bot.send_photo(chat_id=chat_id, photo=f, caption="Sklad - 1 cheki. Tasdiqlaysizmi?", reply_markup=reply_markup)
        os.remove(img1)
        
    if wh_2_items:
        img2 = generate_receipt_image(wh_2_items, "Sklad - 2", "O'rikzor")
        with open(img2, 'rb') as f:
            await bot.send_photo(chat_id=chat_id, photo=f, caption="Sklad - 2 cheki. Tasdiqlaysizmi?", reply_markup=reply_markup)
        os.remove(img2)

async def handle_wizard_confirm(update, context):
    query = update.callback_query
    await query.answer()
    
    # Guruhga yuborish va Odoo ga yozish
    chat_id = update.effective_chat.id
    order = context.user_data['wizard_order']
    group_id = context.user_data['wizard_group_id']
    msg_id = context.user_data['wizard_msg_id']
    
    # Qaysi skladligini captiondan aniqlaymiz
    is_wh_1 = "Sklad - 1" in query.message.caption
    is_wh_2 = "Sklad - 2" in query.message.caption
    
    wh_items = []
    source_wh = 0
    wh_name = ""
    if is_wh_1:
        wh_items = [i for i in order['items'] if i.get('warehouse') == 'Sklad - 1']
        source_wh = 4
        wh_name = "Sklad - 1"
    elif is_wh_2:
        wh_items = [i for i in order['items'] if i.get('warehouse') == 'Sklad - 2']
        source_wh = 7
        wh_name = "Sklad - 2"
        
    if not wh_items:
        await query.message.edit_caption(caption="Xato: Tovarlar topilmadi.")
        return
        
    await query.message.edit_caption(caption=f"Odoo'ga yozilmoqda... Kuting.")
    
    from odoo_client import OdooClient
    from image_generator import generate_receipt_image
    
    client = OdooClient()
    dest_company_id = 2 # Urikzor company ID
    
    items_for_transfer = [{'product_name': i.get('matched_name') or i.get('raw_name'), 'qty': i['qty']} for i in wh_items]
    transfer_res = client.create_intercompany_transfer_bulk(source_warehouse_id=source_wh, dest_company_id=dest_company_id, dest_warehouse_id=3, items=items_for_transfer)
    
    img = generate_receipt_image(wh_items, wh_name, "O'rikzor")
    with open(img, 'rb') as f:
        await context.bot.send_photo(chat_id=group_id, photo=f, caption=f"{wh_name}\n\nOdoo Natijasi:\n{transfer_res}", reply_to_message_id=msg_id)
    os.remove(img)
    
    await query.message.edit_caption(caption=f"✅ {wh_name} uchun tasdiqlandi va guruhga jo'natildi!\nOdoo: {transfer_res}")
    
    import order_queue_manager
    order_queue_manager.release_wizard(context)

async def handle_wizard_cancel(update, context):
    query = update.callback_query
    await query.answer()
    await query.message.edit_caption(caption="❌ Bekor qilindi.")
    
    import order_queue_manager
    order_queue_manager.release_wizard(context)

async def handle_manual_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idx = context.user_data.get('wizard_awaiting_manual_item_idx')
    if idx is not None:
        order = context.user_data['wizard_order']
        order['items'][idx]['raw_name'] = update.message.text
        del context.user_data['wizard_awaiting_manual_item_idx']
        context.user_data['wizard_search_offset'] = 0
        await process_next_product(context.bot, update.message.chat_id, context)
        return True
    return False

def get_wizard_handlers():
    from telegram.ext import CallbackQueryHandler, MessageHandler, filters
    return [
        CallbackQueryHandler(handle_product_variant, pattern="^prod_"),
        CallbackQueryHandler(handle_warehouse_mode, pattern="^(mode_|wh_single_)"),
        CallbackQueryHandler(handle_mixed_warehouse, pattern="^wh_mixed_"),
        CallbackQueryHandler(handle_wizard_confirm, pattern="^wizard_confirm$"),
        CallbackQueryHandler(handle_wizard_cancel, pattern="^wizard_cancel$")
    ]
