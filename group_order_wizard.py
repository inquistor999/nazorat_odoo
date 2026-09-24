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
    import os, json, difflib
    
    keyboard = []
    
    try:
        client = OdooClient()
        matched_names = []
        raw_name = item['raw_name'].lower()
        
        # 1. Load local DB for fuzzy matching
        if os.path.exists('products_db.json'):
            try:
                with open('products_db.json', 'r', encoding='utf-8') as f:
                    local_products = json.load(f)
                    all_names = [str(p['name']) for p in local_products if p.get('name')]
                    
                    # Fuzzy match
                    matches = difflib.get_close_matches(raw_name, [n.lower() for n in all_names], n=15, cutoff=0.2)
                    
                    # Or try word intersection
                    if not matches:
                        raw_words = set(raw_name.split())
                        scored = []
                        for n in all_names:
                            n_words = set(n.lower().split())
                            score = len(raw_words.intersection(n_words))
                            if score > 0:
                                scored.append((score, n))
                        scored.sort(reverse=True)
                        matches = [n for s, n in scored[:15]]
                        
                    # Find original cased names
                    for match in matches:
                        for original in all_names:
                            if original.lower() == match and original not in matched_names:
                                matched_names.append(original)
                                break
            except Exception:
                pass
                
        # Fallback to ilike if fuzzy fails
        domain = []
        if matched_names:
            domain = [('name', 'in', matched_names)]
        else:
            words = item['raw_name'].split()
            for w in words:
                if len(w) >= 3:
                    domain.append(('name', 'ilike', w))
            if not domain:
                domain = [('name', 'ilike', item['raw_name'])]
            
        import asyncio
        products = await asyncio.to_thread(client.models.execute_kw, client.db, client.uid, client.password, 
            'product.product', 'search_read', 
            [domain], 
            {'fields': ['id', 'name', 'qty_available'], 'limit': 20})
            
        if products and isinstance(products, list):
            # FILTER: Skladda borlarni ajratib olamiz (qty_available > 0)
            valid_products = [p for p in products if p.get('qty_available', 0) > 0]
            
            # Agar hammasi 0 bo'lsa (yoki variant umuman topilmasa)
            if not valid_products:
                keyboard.append([InlineKeyboardButton("Variant topilmadi (Yoki Ostatka 0)", callback_data="prod_notfound")])
            else:
                # Slicing for pagination
                paginated = valid_products[offset:offset+4]
                for p in paginated:
                    name = p.get('name', 'Nomsiz')
                    display_name = name[:40] + '...' if len(name) > 40 else name
                    keyboard.append([InlineKeyboardButton(display_name, callback_data=f"prod_{name[:20]}")])
                
                if offset + 4 < len(valid_products):
                    keyboard.append([InlineKeyboardButton("➡️ Yana variantlar (Next)", callback_data="prod_next_page")])
                elif offset > 0:
                    keyboard.append([InlineKeyboardButton("Variant topilmadi", callback_data="prod_notfound")])
                else:
                    keyboard.append([InlineKeyboardButton("Variant topilmadi", callback_data="prod_notfound")])
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
    try:
        order = context.user_data['wizard_order']
        
        if 'wizard_validation_idx' not in context.user_data:
            context.user_data['wizard_validation_idx'] = 0
            
        items = order['items']
        idx = context.user_data['wizard_validation_idx']
        
        from odoo_client import OdooClient
        client = OdooClient()
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        # Qotib qolmasligi uchun xabar yuboramiz
        if idx == 0:
            await bot.send_message(chat_id=chat_id, text="⏳ Qoldiq va bronlar tekshirilmoqda, iltimos kuting...")
        
        while idx < len(items):
            item = items[idx]
            wh_name = item.get('warehouse')
            if not wh_name:
                idx += 1
                context.user_data['wizard_validation_idx'] = idx
                continue
                
            wh_id = 4 if wh_name == 'Sklad - 1' else 7
            p_name = item.get('matched_name') or item.get('raw_name')
            req_qty = float(item['qty'])
            
            import asyncio
            res = await asyncio.to_thread(client.check_inventory_and_get_reservations, p_name, req_qty, wh_id)
            if res['status'] == 'error':
                await bot.send_message(chat_id=chat_id, text=f"❌ Xato: {res['msg']}")
                idx += 1
                context.user_data['wizard_validation_idx'] = idx
                continue
                
            if res['status'] == 'shortage':
                if not res['reservations']:
                    # ZERO STOCK REPLACEMENT LOGIC
                    if res['free_qty'] == 0:
                        text = f"⚠️ <b>{p_name}</b> omborda ({wh_name}) mutlaqo qolmagan (0 kg).\n\nBuning o'rniga qaysi muqobil tovarni qo'shamiz?"
                        
                        # Qidiruv
                        offset = context.user_data.get('wizard_zero_search_offset', 0)
                        raw_name = item.get('raw_name', p_name)
                        
                        import asyncio
                        all_products = await asyncio.to_thread(client.search_products, raw_name, 50)
                        products = all_products[offset:offset+4]
                        has_more = len(all_products) > (offset + 4)
                        
                        keyboard = []
                        for p in products:
                            short_name = p['name'][:40]
                            keyboard.append([InlineKeyboardButton(short_name, callback_data=f"rep_{p['id']}")])
                        
                        if has_more:
                            keyboard.append([InlineKeyboardButton("➡️ Boshqa variantlar", callback_data="rep_next_page")])
                            
                        keyboard.append([InlineKeyboardButton("🗑 Tovarni otmen qilish", callback_data="rep_cancel")])
                        
                        context.user_data['wizard_current_replace_idx'] = idx
                        context.user_data['wizard_current_replace_search'] = products
                        
                        await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                        return # Kutamiz
                    else:
                        await bot.send_message(chat_id=chat_id, text=f"⚠️ Diqqat! '{p_name}' qoldig'i faqat {res['free_qty']} kg bor. Boshqa hech kimda bron qilinmagan. Zakaz chala qolishi mumkin!")
                        idx += 1
                        context.user_data['wizard_validation_idx'] = idx
                        continue
                    
                res_idx = context.user_data.get('wizard_res_idx', 0)
                
                if res_idx >= len(res['reservations']):
                    await bot.send_message(chat_id=chat_id, text=f"Tugadi: '{p_name}' bo'yicha boshqa bron topilmadi.")
                    idx += 1
                    context.user_data['wizard_validation_idx'] = idx
                    context.user_data['wizard_res_idx'] = 0
                    continue
                    
                r = res['reservations'][res_idx]
                
                text = f"📦 Tovar: <b>{p_name}</b>\n"
                text += f"🏢 Ombor: {wh_name}\n"
                text += f"✅ Erkin qoldiq: {res['free_qty']} kg\n"
                text += f"❌ Yetishmovchilik: {res['shortage']} kg\n\n"
                text += f"🔍 Qidiruv natijasi: Menejer <b>'{r['manager']}'</b> bronida (Hujjat: {r['ref']}) <b>{r['qty']}</b> bor.\n\n"
                text += f"Shundan {res['shortage']} yechib olaylikmi?"
                
                keyboard = [
                    [InlineKeyboardButton(f"✅ Xa, chistichno yech ({res['shortage']} ni)", callback_data="res_steal")],
                    [InlineKeyboardButton("⏭ Yo'q, boshqa kimni bronida bor?", callback_data="res_next")],
                    [InlineKeyboardButton("🗑 Tovar otmen (Zakazdan ob tashla)", callback_data="res_cancel")]
                ]
                
                context.user_data['wizard_current_shortage'] = res['shortage']
                context.user_data['wizard_current_res'] = r
                
                await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                return 
                
            idx += 1
            context.user_data['wizard_validation_idx'] = idx
            
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
            import os
            with open(img1, 'rb') as f:
                await bot.send_photo(chat_id=chat_id, photo=f, caption="Sklad - 1 cheki. Tasdiqlaysizmi?", reply_markup=reply_markup)
            os.remove(img1)
            
        if wh_2_items:
            img2 = generate_receipt_image(wh_2_items, "Sklad - 2", "O'rikzor")
            import os
            with open(img2, 'rb') as f:
                await bot.send_photo(chat_id=chat_id, photo=f, caption="Sklad - 2 cheki. Tasdiqlaysizmi?", reply_markup=reply_markup)
            os.remove(img2)
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        await bot.send_message(chat_id=chat_id, text=f"❌ Kritik xato: {e}\n{err[:3000]}")
async def handle_replace_product(update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "rep_next_page":
        context.user_data['wizard_zero_search_offset'] = context.user_data.get('wizard_zero_search_offset', 0) + 4
        await query.message.delete()
        await finalize_order(context.bot, update.effective_chat.id, context)
        return
        
    if query.data == "rep_cancel":
        idx = context.user_data['wizard_current_replace_idx']
        order = context.user_data['wizard_order']
        item = order['items'][idx]
        p_name = item.get('matched_name') or item.get('raw_name')
        order['items'].pop(idx)
        
        await query.message.edit_text(f"🗑 {p_name} zakazdan olib tashlandi!")
        
        # Qayta tekshiruv
        context.user_data['wizard_zero_search_offset'] = 0
        await finalize_order(context.bot, update.effective_chat.id, context)
        return
        
    # Tugma bosilganda (Product ID keladi)
    p_id = int(query.data.replace("rep_", ""))
    products = context.user_data.get('wizard_current_replace_search', [])
    selected_name = None
    for p in products:
        if p['id'] == p_id:
            selected_name = p['name']
            break
            
    if not selected_name:
        await query.message.edit_text("❌ Xatolik: Tovar topilmadi.")
        return
        
    idx = context.user_data['wizard_current_replace_idx']
    order = context.user_data['wizard_order']
    
    old_name = order['items'][idx].get('matched_name') or order['items'][idx].get('raw_name')
    order['items'][idx]['matched_name'] = selected_name
    
    await query.message.edit_text(f"✅ {old_name} o'rniga <b>{selected_name}</b> qo'shildi!", parse_mode='HTML')
    
    context.user_data['wizard_zero_search_offset'] = 0
    await finalize_order(context.bot, update.effective_chat.id, context)

async def handle_res_steal(update, context):
    query = update.callback_query
    await query.answer()
    
    shortage = context.user_data['wizard_current_shortage']
    r = context.user_data['wizard_current_res']
    
    from odoo_client import OdooClient
    client = OdooClient()
    
    steal_qty = min(shortage, r['qty'])
    
    # 2-Bosqichli tekshiruv uchun yuklanish xabari
    await query.message.edit_text(f"⏳ {r['manager']} ning {r['ref']} bronidan {steal_qty} kg yechilmoqda...\nQat'iy tekshiruv (2-step verification) o'tkazilmoqda!")
    
    # Non-blocking qilib chaqiramiz:
    import asyncio
    success = await asyncio.to_thread(client.steal_reservation, r['move_id'], r['sale_line_id'], steal_qty)
    
    if success:
        await query.message.edit_text(f"✅ MUVAFFAQIYATLI: {r['manager']} ning {r['ref']} bronidan {steal_qty} kg yechib olindi va Erkin Qoldiq ko'paydi!")
        context.user_data['wizard_res_idx'] = 0
        await finalize_order(context.bot, update.effective_chat.id, context)
    else:
        await query.message.edit_text(f"❌ FOJIALI XATO!\nOdoo bazasida brondan tovar yechilmadi va erkin qoldiq ko'paymadi! Shuning uchun minusga kirmasligi uchun butun tranzaksiya to'xtatildi! Iltimos bazani tekshiring.")
        import order_queue_manager
        order_queue_manager.release_wizard(context)
        return
    
async def handle_res_next(update, context):
    query = update.callback_query
    await query.answer()
    
    context.user_data['wizard_res_idx'] = context.user_data.get('wizard_res_idx', 0) + 1
    await query.message.delete()
    await finalize_order(context.bot, update.effective_chat.id, context)
    
async def handle_res_cancel(update, context):
    query = update.callback_query
    await query.answer()
    
    idx = context.user_data['wizard_validation_idx']
    order = context.user_data['wizard_order']
    
    item = order['items'][idx]
    p_name = item.get('matched_name') or item.get('raw_name')
    
    # Zakazdan olib tashlaymiz
    order['items'].pop(idx)
    
    await query.message.edit_text(f"🗑 {p_name} zakazdan olib tashlandi!")
    
    # Biz pop qilganimiz uchun idx ni oshirmaymiz (xuddi shu indeksda endi keyingi tovar turadi)
    context.user_data['wizard_res_idx'] = 0
    await finalize_order(context.bot, update.effective_chat.id, context)

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
    import asyncio
    transfer_res = await asyncio.to_thread(client.create_intercompany_transfer_bulk, source_wh, dest_company_id, 3, items_for_transfer)
    
    img = generate_receipt_image(wh_items, wh_name, "O'rikzor")
    with open(img, 'rb') as f:
        await context.bot.send_photo(chat_id=group_id, photo=f, caption=f"{wh_name}", reply_to_message_id=msg_id)
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
        CallbackQueryHandler(handle_res_steal, pattern="^res_steal$"),
        CallbackQueryHandler(handle_res_next, pattern="^res_next$"),
        CallbackQueryHandler(handle_res_cancel, pattern="^res_cancel$"),
        CallbackQueryHandler(handle_replace_product, pattern="^rep_"),
        CallbackQueryHandler(handle_wizard_confirm, pattern="^wizard_confirm$"),
        CallbackQueryHandler(handle_wizard_cancel, pattern="^wizard_cancel$")
    ]
