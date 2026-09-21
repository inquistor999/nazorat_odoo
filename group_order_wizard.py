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

async def start_group_order_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE, order_data: dict, original_message_id: int, group_id: int):
    """
    Triggered from main.py when a group order is detected.
    """
    admin_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not admin_chat_id:
        return

    context.user_data['wizard_order'] = order_data
    context.user_data['wizard_msg_id'] = original_message_id
    context.user_data['wizard_group_id'] = group_id
    context.user_data['wizard_current_item_idx'] = 0

    await process_next_product(context.bot, admin_chat_id, context)

async def process_next_product(bot, chat_id, context):
    order = context.user_data['wizard_order']
    idx = context.user_data['wizard_current_item_idx']
    
    if idx >= len(order['items']):
        return await check_stock_for_order(bot, chat_id, context)
        
    item = order['items'][idx]
    
    # Mock search
    keyboard = [
        [InlineKeyboardButton("Variant 1", callback_data="prod_var_1")],
        [InlineKeyboardButton("Variant 2", callback_data="prod_var_2")],
        [InlineKeyboardButton("Variant 3", callback_data="prod_var_3")],
        [InlineKeyboardButton("Variant 4", callback_data="prod_var_4")],
        [InlineKeyboardButton("Bu emas", callback_data="prod_next_page")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"📦 Guruhdan zakaz:\n'{item['raw_name']}' ({item['qty']} kg)\nOdoo dan to'g'ri nomni tanlang:"
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

async def handle_product_variant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "prod_next_page":
        await query.message.edit_text("Keyingi variantlar...")
        return
        
    order = context.user_data['wizard_order']
    idx = context.user_data['wizard_current_item_idx']
    order['items'][idx]['matched_name'] = query.data
    context.user_data['wizard_current_item_idx'] += 1
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
    group_id = context.user_data['wizard_group_id']
    msg_id = context.user_data['wizard_msg_id']
    
    wh_1_items = [i for i in order['items'] if i.get('warehouse') == 'Sklad - 1']
    wh_2_items = [i for i in order['items'] if i.get('warehouse') == 'Sklad - 2']
    
    await bot.send_message(chat_id=chat_id, text="✅ Zakaz tayyor, guruhga yuborilmoqda...")
    
    if wh_1_items:
        img = generate_receipt_image(f"{len(wh_1_items)} xil tovar", sum(float(i['qty']) for i in wh_1_items), "Sklad - 1", "O'rikzor")
        await bot.send_photo(chat_id=group_id, photo=open(img, 'rb'), caption="Sklad - 1", reply_to_message_id=msg_id)
        os.remove(img)
        
    if wh_2_items:
        img = generate_receipt_image(f"{len(wh_2_items)} xil tovar", sum(float(i['qty']) for i in wh_2_items), "Sklad - 2", "O'rikzor")
        await bot.send_photo(chat_id=group_id, photo=open(img, 'rb'), caption="Sklad - 2", reply_to_message_id=msg_id)
        os.remove(img)

def get_wizard_conversation_handler():
    from telegram.ext import CallbackQueryHandler, MessageHandler, filters
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_product_variant, pattern="^prod_")],
        states={
            SELECTING_PRODUCT_VARIANT: [
                CallbackQueryHandler(handle_product_variant, pattern="^prod_")
            ],
            SELECTING_WAREHOUSE_MODE: [
                CallbackQueryHandler(handle_warehouse_mode, pattern="^(mode_|wh_single_)")
            ],
            SELECTING_WAREHOUSE_FOR_ITEM: [
                CallbackQueryHandler(handle_mixed_warehouse, pattern="^wh_mixed_")
            ]
        },
        fallbacks=[]
    )
