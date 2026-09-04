import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from telegram.request import HTTPXRequest
import config
from odoo_client import OdooClient
from analysis import calculate_reorder_qty, create_sales_history_chart, extract_package_info
from excel_exporter import generate_monthly_sales_excel, generate_reorder_excel

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

WAITING_FOR_PASSWORD = 1
WAITING_FOR_PRODUCT_NAME = 2
WAITING_FOR_PRODUCT_CONFIRMATION = 3
WAITING_FOR_MONTHS = 4

async def send_with_retry(send_func, retries=3, delay=3):
    import asyncio
    for attempt in range(retries):
        try:
            return await send_func()
        except Exception as e:
            if attempt < retries - 1:
                logging.warning(f"Yuborishda xato: {e}. {delay}s dan keyin qayta uriniladi...")
                await asyncio.sleep(delay)
            else:
                raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start bosilganda kompaniya tanlash menyusi"""
    keyboard = [
        [InlineKeyboardButton("🏢 B2B", callback_data="comp_3")],
        [InlineKeyboardButton("🏪 O'rikzor", callback_data="comp_2")],
        [InlineKeyboardButton("🏬 Qo'qon", callback_data="comp_4")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_name = update.effective_user.first_name if update.effective_user else "foydalanuvchi"
    welcome_text = (
        f"👋 <b>Salom {user_name}! Xush kelibsiz.</b>\n\n"
        "🤖 <i>Men sizning shaxsiy Odoo yordamchingizman.</i>\n"
        "👇 Iltimos, hisobot olish uchun filialni tanlang:"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
        
    return WAITING_FOR_PASSWORD

async def handle_company_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    comp_id = int(query.data.split('_')[1])
    context.user_data['selected_company'] = comp_id
    
    comp_names = {3: 'B2B', 2: "O'rikzor", 4: "Qo'qon"}
    context.user_data['company_name'] = comp_names.get(comp_id, "Noma'lum")
    
    await query.message.edit_text(f"🔒 <b>{comp_names[comp_id]}</b> filiali uchun parolni kiriting:", parse_mode='HTML')
    return WAITING_FOR_PASSWORD

async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    comp_id = context.user_data.get('selected_company')
    
    passwords = {
        3: '9706500',
        2: 'shovkat123',
        4: 'zafar123'
    }
    
    if password == passwords.get(comp_id):
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        keyboard = [[InlineKeyboardButton("🔙 Ortga qaytish", callback_data="menu_start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("❌ Noto'g'ri parol! Qaytadan kiriting yoki ortga qayting:", reply_markup=reply_markup)
        return WAITING_FOR_PASSWORD

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comp_id = context.user_data.get('selected_company')
    comp_name = context.user_data.get('company_name')
    
    if comp_id == 3: # B2B
        keyboard = [
            [InlineKeyboardButton("📦 Tortilib qolgan tovarlar", callback_data="menu_check_inventory")],
            [InlineKeyboardButton("📊 Tovar statistikasi", callback_data="menu_product_stats")]
        ]
    else: # O'rikzor, Qo'qon
        keyboard = [
            [InlineKeyboardButton("📅 Oylik statistika (Excel)", callback_data="menu_monthly_stats")]
        ]
        
    # Orqaga qaytish (Kompaniya tanlashga)
    keyboard.append([InlineKeyboardButton("🔙 Boshqa filialni tanlash", callback_data="menu_start")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"✅ Parol qabul qilindi.\n\n<b>{comp_name}</b> filiali menyusi:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_start":
        return await start(update, context)
        
    if query.data == "menu_back":
        await show_main_menu(update, context)
        return ConversationHandler.END
        
    if query.data == "menu_check_inventory":
        # Eski logikani chaqirish (faylda)
        await check_inventory_logic(query.message, context)
        return ConversationHandler.END
        
    if query.data == "menu_product_stats":
        await query.message.reply_text("Qidirmoqchi bo'lgan tovaringiz nomini yozing:")
        return WAITING_FOR_PRODUCT_NAME
        
    if query.data == "menu_monthly_stats":
        await query.message.reply_text("Necha oylik statistika kerak? Raqam kiriting (masalan: 4):")
        return WAITING_FOR_MONTHS

async def handle_months(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text.isdigit():
        await update.message.reply_text("❌ Iltimos, faqat raqam kiriting (masalan: 4):")
        return WAITING_FOR_MONTHS
        
    months = int(text)
    comp_id = context.user_data.get('selected_company')
    comp_name = context.user_data.get('company_name')
    
    await update.message.reply_text(f"⏳ {months} oylik ma'lumotlar yig'ilmoqda. Iltimos biroz kuting, bu bir necha daqiqa olishi mumkin...")
    
    from excel_exporter import generate_monthly_sales_excel
    import asyncio
    try:
        excel_file = await asyncio.to_thread(generate_monthly_sales_excel, comp_id, months, comp_name)
        if excel_file:
            await update.message.reply_document(
                document=excel_file,
                filename=f"{comp_name}_{months}_oylik_statistika.xlsx",
                caption=f"📊 <b>{comp_name}</b> filialining oxirgi {months} oy ichidagi barcha sotuvlar statistikasi.",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(f"Oxirgi {months} oy ichida hech qanday sotuv topilmadi.")
    except Exception as e:
        logging.error(f"Excel yaratishda xato: {e}", exc_info=True)
        await update.message.reply_text("Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")
        
    await show_main_menu(update, context)
    return ConversationHandler.END

# ----------------- B2B Tovar qidirish logikasi -----------------

async def handle_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_name = update.message.text
    
    await update.message.reply_text("Odoo bazasidan ma'lumot izlanmoqda. Iltimos kuting...")
    
    try:
        import asyncio
        odoo = OdooClient()
        matches = await asyncio.to_thread(odoo.search_products, product_name, 20)
        
        if not matches:
            keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"Kechirasiz, '{product_name}' ga o'xshash tovar topilmadi. Qaytadan urinib ko'ring yoki Ortga qayting.",
                reply_markup=reply_markup
            )
            return WAITING_FOR_PRODUCT_NAME
            
        context.user_data['search_matches'] = matches
        context.user_data['search_index'] = 0
        
        await show_current_match(update, context, update.message)
        return WAITING_FOR_PRODUCT_CONFIRMATION
        
    except Exception as e:
        logging.error(f"Qidiruvda xatolik: {e}", exc_info=True)
        keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Xatolik yuz berdi: {str(e)}", reply_markup=reply_markup)
        return WAITING_FOR_PRODUCT_NAME

async def show_current_match(update: Update, context: ContextTypes.DEFAULT_TYPE, message_obj=None):
    matches = context.user_data.get('search_matches', [])
    index = context.user_data.get('search_index', 0)
    
    if index >= len(matches):
        keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "Boshqa o'xshash tovar topilmadi. Iltimos nomini aniqroq yozing."
        if update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
        else:
            await message_obj.reply_text(text, reply_markup=reply_markup)
        return WAITING_FOR_PRODUCT_NAME
        
    match = matches[index]
    text = f"📦 <b>{match['name']}</b>\n\nSiz shu tovarni qidirdingizmi?"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ To'g'ri", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Noto'g'ri", callback_data="confirm_no")
        ],
        [InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await message_obj.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_back":
        await show_main_menu(update, context)
        return ConversationHandler.END
        
    if query.data == "confirm_no":
        context.user_data['search_index'] += 1
        return await show_current_match(update, context)
        
    if query.data == "confirm_yes":
        matches = context.user_data.get('search_matches', [])
        index = context.user_data.get('search_index', 0)
        match = matches[index]
        
        await query.message.edit_text(f"<b>{match['name']}</b> statistikasi yuklanmoqda...", parse_mode='HTML')
        await send_product_statistics(query.message, match['id'], match['name'])
        return ConversationHandler.END

async def send_product_statistics(message_obj, product_id, name):
    try:
        odoo = OdooClient()
        pkg_info = extract_package_info(name)
        pkg_weight_kg = pkg_info['weight_kg']
        is_gram = pkg_info['is_gram']
        
        # Odoo calls wrapped in asyncio.to_thread
        import asyncio
        monthly_sales_5m = await asyncio.to_thread(odoo.get_monthly_sales, product_id, 5)
        stats = await asyncio.to_thread(odoo.get_sales_statistics, product_id, 5)
        purchase_info = await asyncio.to_thread(odoo.get_last_purchase, product_id)
        
        manager_sales = stats['manager_sales']
        total_kg_all_managers = sum(manager_sales.values())
        if is_gram:
            total_kg_all_managers = total_kg_all_managers * pkg_weight_kg
            
        manager_text = f"👥 <b>Menenjerlar:</b> Jami {len(manager_sales)} ta ({round(total_kg_all_managers, 2)} kg)\n"
        for mgr, qty in manager_sales.items():
            mgr_kg = qty * pkg_weight_kg if is_gram else qty
            manager_text += f"  👤 {mgr} <i>({round(mgr_kg, 2)}kg)</i>\n"
            
        monthly_text = "📅 <b>Oyma-oy sotuvlar (5 oy):</b>\n"
        monthly_sales_chart_data = {}
        for m, qty in monthly_sales_5m.items():
            kg_qty = round(qty * pkg_weight_kg if is_gram else qty, 2)
            monthly_text += f"  🔹 {m} - <b>{kg_qty} kg</b>\n"
            monthly_sales_chart_data[m] = kg_qty
            
        min_price = stats.get('min_price')
        max_price = stats.get('max_price')
        min_order = stats.get('min_order', "")
        max_order = stats.get('max_order', "")
        
        price_text = "💰 <b>Narx ko'rsatkichlari:</b>\n"
        if min_price is not None:
            price_text += f"  ⬇️ Eng arzon: <b>{min_price} $</b> <i>({min_order})</i>\n"
        if max_price is not None:
            price_text += f"  ⬆️ Eng qimmat: <b>{max_price} $</b> <i>({max_order})</i>\n"
            
        purchase_text = "🚚 <b>Kirim ma'lumoti:</b>\n"
        if purchase_info:
            p_qty = purchase_info['qty']
            p_qty_kg = round(p_qty * pkg_weight_kg if is_gram else p_qty, 2)
            p_price = purchase_info['price']
            p_partner = purchase_info['partner']
            p_date = purchase_info['date']
            purchase_text += f"  🔄 <b>Oxirgi prixod:</b> {p_date}\n  📦 <b>Hajmi:</b> {p_qty_kg} kg\n  💵 <b>Narx:</b> {p_price} $\n  🏢 <b>Ta'minotchi:</b> {p_partner}\n"
        else:
            purchase_text += "  ⚠️ Prixod qilingani haqida ma'lumot topilmadi.\n"
            
        final_msg = (
            f"📊 <b><u>{name}</u> statistikasi</b> (oxirgi 5 oy)\n\n"
            f"{manager_text}\n"
            f"{monthly_text}\n"
            f"{price_text}\n"
            f"{purchase_text}"
        )
        
        chart_buf = await asyncio.to_thread(create_sales_history_chart, name, monthly_sales_chart_data)
        
        keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message_obj.reply_photo(photo=chart_buf, caption=final_msg, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Statistikada xatolik: {e}", exc_info=True)
        keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message_obj.reply_text(f"Xatolik yuz berdi: {str(e)}", reply_markup=reply_markup)


# ----------------- Inventory Logic (Old method) -----------------
async def check_inventory_logic(message_obj, context):
    await message_obj.reply_text("Odoo bazasidan barcha mahsulotlar ma'lumotlari yuklanmoqda... Bu bir necha daqiqa vaqt olishi mumkin.")
    try:
        product_names = config.get_tracked_product_names()
        if not product_names:
            await message_obj.reply_text("Kuzatiladigan tovarlar ro'yxati bo'sh!")
            return

        from odoo_client import OdooClient
        odoo = OdooClient()
        items_to_reorder = []
        all_items = []
        
        import asyncio
        batch_data = await asyncio.to_thread(odoo.get_batch_inventory_data, product_names, 30)
        
        for name in product_names:
            try:
                data = batch_data.get(name)
                if not data:
                    continue
                    
                stock_qty = data['stock_qty']
                sales_qty = data['sales_qty']
                
                reorder_info = calculate_reorder_qty(name, stock_qty, sales_qty)
                item_data = {
                    'name': name,
                    'stock_qty': stock_qty,
                    'sales_qty': sales_qty,
                    'sales_b2b': data.get('sales_b2b', 0.0),
                    'transfer_urikzor': data.get('transfer_urikzor', 0.0),
                    'transfer_qoqon': data.get('transfer_qoqon', 0.0),
                    'reorder_qty': reorder_info['reorder_qty'],
                    'days_left': reorder_info['days_left'],
                    'pieces': reorder_info.get('pieces', 0)
                }
                
                all_items.append(item_data)
                
                if reorder_info['reorder_qty'] > 0:
                    items_to_reorder.append(item_data)
                    
            except Exception as e:
                logging.error(f"{name} xato: {e}")
                
        if not items_to_reorder:
            await send_with_retry(lambda: message_obj.reply_text("🎉 Hamma tovarlar yetarli darajada! Zakaz qilishga ehtiyoj yo'q (Lekin hisobotni quyidagi Excel orqali ko'rishingiz mumkin)."))
        
        keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Excel faylni yaratish va yuborish
        import asyncio
        excel_file = await asyncio.to_thread(generate_reorder_excel, all_items)
        if excel_file:
            await send_with_retry(lambda: message_obj.reply_document(
                document=excel_file,
                filename="Zakaz_Ro'yxati.xlsx",
                caption="📊 <b>Barcha tovarlar hisoboti (Excel)</b>\n\nQuyidagi faylda barcha tovarlarning:\n🔹 Hozirgi qoldig'i\n🔹 O'rikzor, Qo'qon va B2B sotuvlari (1 oylik)\n🔹 Qoldiq necha kunga yetishi\n🔹 Qancha zakaz qilish kerakligi batafsil yozilgan.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            ))
        else:
            await send_with_retry(lambda: message_obj.reply_text("Hech qanday ma'lumot topilmadi.", reply_markup=reply_markup))

    except Exception as e:
        logging.error(f"Xatolik: {e}", exc_info=True)
        keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
        await message_obj.reply_text(f"Tizimda xatolik yuz berdi: {str(e)}", reply_markup=InlineKeyboardMarkup(keyboard))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Amaliyot bekor qilindi. /start ni bosing.")
    return ConversationHandler.END

def run_dummy_server():
    class DummyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Bot is running!")
    
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    logging.info(f"Yolg'on web server {port}-portda ishga tushdi (Render Free tier uchun)")
    server.serve_forever()

def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("XATOLIK: .env faylida TELEGRAM_BOT_TOKEN kiritilmagan!")
        return

    render_url = os.environ.get('RENDER_EXTERNAL_URL')
    
    # Render bepul versiyasida uxlab qolmaslik uchun: 
    # Agar webhook bo'lsa u holda ptb o'zi server ko'taradi, shuning uchun dummy_server shart emas
    if not render_url:
        server_thread = threading.Thread(target=run_dummy_server, daemon=True)
        server_thread.start()

    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=60,
        write_timeout=60,
        connect_timeout=30
    )

    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).request(request).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(menu_callback, pattern='^menu_'),
            CallbackQueryHandler(handle_company_selection, pattern='^comp_')
        ],
        states={
            WAITING_FOR_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password),
                CallbackQueryHandler(handle_company_selection, pattern='^comp_'),
                CallbackQueryHandler(menu_callback, pattern='^menu_')
            ],
            WAITING_FOR_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_name)],
            WAITING_FOR_PRODUCT_CONFIRMATION: [CallbackQueryHandler(handle_confirmation)],
            WAITING_FOR_MONTHS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_months)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)]
    )

    application.add_handler(conv_handler)
    
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
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
