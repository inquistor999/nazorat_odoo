import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from telegram.request import HTTPXRequest
import config
from odoo_client import OdooClient
from analysis import calculate_reorder_qty, create_sales_history_chart, extract_package_info

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

WAITING_FOR_PRODUCT_NAME = 1

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
    """/start bosilganda salomlashish va menyu chiqarish"""
    keyboard = [
        [InlineKeyboardButton("Tortilib qolgan tovarlar", callback_data="menu_check_inventory")],
        [InlineKeyboardButton("Tovar statistikasi", callback_data="menu_product_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_name = update.effective_user.first_name if update.effective_user else "foydalanuvchi"
    welcome_text = (
        f"👋 <b>Salom {user_name}! Xush kelibsiz.</b>\n\n"
        "🤖 <i>Men sizning shaxsiy Odoo yordamchingizman.</i>\n"
        "👇 Iltimos, quyidagi menyudan kerakli bo'limni tanlang:"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
        
    return ConversationHandler.END

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_check_inventory":
        await check_inventory_logic(query.message, context)
        return ConversationHandler.END
    elif query.data == "menu_product_stats":
        await query.message.reply_text("Menga tovar to'liq nomini yuboring:")
        return WAITING_FOR_PRODUCT_NAME
    elif query.data == "menu_back":
        await start(update, context)
        return ConversationHandler.END
    elif query.data == "make_order":
        order_list_text = context.user_data.get('order_list', [])
        today = datetime.datetime.now().strftime("%d.%m.%Y")
        final_msg = f"Zakaz : {today}\n" + "\n".join(order_list_text)
        await query.edit_message_text(text=final_msg)
        return ConversationHandler.END

async def check_inventory_logic(message, context: ContextTypes.DEFAULT_TYPE):
    chat_id = message.chat_id
    await message.reply_text(
        "Odoo bazasiga ulanmoqda va tovarlar tahlil qilinmoqda...\n"
        "Bu bir necha daqiqa olishi mumkin, iltimos kuting."
    )

    try:
        odoo = OdooClient()
        tracked_products = config.get_tracked_product_names()
        if not tracked_products:
            await message.reply_text("Kuzatiladigan tovarlar ro'yxati (tracked_products.txt) bo'sh yoki topilmadi.")
            return

        order_list_text = []

        for product_name in tracked_products:
            product_info = odoo.get_product_info_by_name(product_name)
            if not product_info:
                logging.info(f"Topilmadi (o'tkazildi): {product_name}")
                continue

            name = product_info['name']
            product_id = product_info['id']
            current_stock = round(product_info['qty_available'], 2)

            monthly_sales = odoo.get_monthly_sales(product_id, num_months=3)
            sales_90d = odoo.get_sales_total_90d(product_id)

            pkg_info = extract_package_info(name)

            if pkg_info['is_gram']:
                pkg_weight_kg = pkg_info['weight_kg']
                monthly_sales_display = {}
                for m, dona_qty in monthly_sales.items():
                    kg_qty = round(dona_qty * pkg_weight_kg, 2)
                    monthly_sales_display[m] = f"{int(dona_qty)} sht ({kg_qty} kg)"
                sales_90d_kg = sales_90d * pkg_weight_kg
                monthly_sales_chart = {m: round(v * pkg_weight_kg, 2) for m, v in monthly_sales.items()}
            else:
                monthly_sales_display = {m: f"{v} kg" for m, v in monthly_sales.items()}
                sales_90d_kg = sales_90d
                monthly_sales_chart = monthly_sales

            analysis = calculate_reorder_qty(name, current_stock, sales_90d_kg)
            reorder_qty = analysis['reorder_qty']
            pieces = analysis.get('pieces', 0)

            if reorder_qty > 0:
                if pieces > 0:
                    reorder_text = f"{reorder_qty} kg ({pieces} sht)"
                else:
                    reorder_text = f"{reorder_qty} kg"

                months_text = "".join([f"{m} - {v}\n" for m, v in monthly_sales_display.items()])

                msg = (
                    f"📦 <b>Zakaz berish kerak:</b> {name}\n\n"
                    f"📊 <b>Hozirgi qoldiq:</b> {current_stock} kg\n"
                    f"📈 <b>O'rtacha kunlik sotuv:</b> {analysis['daily_sales']} kg\n\n"
                    f"📅 <b>Oxirgi 3 oy natijasi:</b>\n"
                    f"<i>{months_text}</i>\n"
                    f"🚚 <i>(2 kunlik yo'l va 1 oylik zaxira uchun)</i>\n\n"
                    f"🛒 <b>Tavsiya etiladigan zakaz miqdori:</b>\n"
                    f"👉 <b>{reorder_text}</b> 👈"
                )

                chart_buf = create_sales_history_chart(name, monthly_sales_chart)
                async def send_photo(c=chat_id, buf=chart_buf, m=msg):
                    return await context.bot.send_photo(chat_id=c, photo=buf, caption=m, parse_mode='HTML')
                await send_with_retry(send_photo)
                order_list_text.append(f"{name} - {reorder_text}")

        if order_list_text:
            context.user_data['order_list'] = order_list_text
            keyboard = [
                [InlineKeyboardButton("ZAKAZ BERISH", callback_data="make_order")],
                [InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Tahlil tugadi. Jami {len(order_list_text)} ta tovardan zakaz berish kerak.",
                reply_markup=reply_markup
            )
        else:
            keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=chat_id,
                text="Barcha tovarlar yetarli! Hozircha zakaz berish shart emas.",
                reply_markup=reply_markup
            )

    except Exception as e:
        logging.error(f"Xatolik: {e}", exc_info=True)
        await message.reply_text(
            f"Xatolik yuz berdi: {str(e)}\n\n"
            "Odoo manzili va login parolingizni tekshiring."
        )

async def handle_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    product_name = update.message.text
    chat_id = update.message.chat_id
    
    await update.message.reply_text("Odoo bazasidan ma'lumot izlanmoqda. Iltimos kuting...")
    
    try:
        odoo = OdooClient()
        product_info = odoo.get_product_info_by_name(product_name)
        if not product_info:
            await update.message.reply_text(f"Kechirasiz, '{product_name}' nomli tovar Odoo bazasidan topilmadi. Qaytadan urinib ko'ring yoki /start bosib menyuga qayting.")
            return WAITING_FOR_PRODUCT_NAME
            
        product_id = product_info['id']
        name = product_info['name']
        pkg_info = extract_package_info(name)
        pkg_weight_kg = pkg_info['weight_kg']
        is_gram = pkg_info['is_gram']
        
        # Odoo calls
        monthly_sales_5m = odoo.get_monthly_sales(product_id, num_months=5)
        stats = odoo.get_sales_statistics(product_id, num_months=5)
        purchase_info = odoo.get_last_purchase(product_id)
        
        # 1. Manager sales text
        manager_sales = stats['manager_sales']
        total_kg_all_managers = sum(manager_sales.values())
        if is_gram:
            total_kg_all_managers = total_kg_all_managers * pkg_weight_kg
            
        manager_text = f"👥 <b>Menenjerlar:</b> Jami {len(manager_sales)} ta ({round(total_kg_all_managers, 2)} kg)\n"
        for mgr, qty in manager_sales.items():
            mgr_kg = qty * pkg_weight_kg if is_gram else qty
            manager_text += f"  👤 {mgr} <i>({round(mgr_kg, 2)}kg)</i>\n"
            
        # 2. Monthly sales formatting
        monthly_text = "📅 <b>Oyma-oy sotuvlar (5 oy):</b>\n"
        monthly_sales_chart_data = {}
        for m, qty in monthly_sales_5m.items():
            kg_qty = round(qty * pkg_weight_kg if is_gram else qty, 2)
            monthly_text += f"  🔹 {m} - <b>{kg_qty} kg</b>\n"
            monthly_sales_chart_data[m] = kg_qty
            
        # 3. Min / Max price
        min_price = stats.get('min_price')
        max_price = stats.get('max_price')
        min_order = stats.get('min_order', "")
        max_order = stats.get('max_order', "")
        
        price_text = "💰 <b>Narx ko'rsatkichlari:</b>\n"
        if min_price is not None:
            price_text += f"  ⬇️ Eng arzon: <b>{min_price} $</b> <i>({min_order})</i>\n"
        if max_price is not None:
            price_text += f"  ⬆️ Eng qimmat: <b>{max_price} $</b> <i>({max_order})</i>\n"
            
        # 4. Last purchase
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
            
        # Combine everything
        final_msg = (
            f"📊 <b><u>{name}</u> statistikasi</b> (oxirgi 5 oy)\n\n"
            f"{manager_text}\n"
            f"{monthly_text}\n"
            f"{price_text}\n"
            f"{purchase_text}"
        )
        
        chart_buf = create_sales_history_chart(name, monthly_sales_chart_data)
        
        keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_photo(photo=chart_buf, caption=final_msg, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Statistikada xatolik: {e}", exc_info=True)
        keyboard = [[InlineKeyboardButton("Ortga qaytish 🔙", callback_data="menu_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"Xatolik yuz berdi: {str(e)}", reply_markup=reply_markup)
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Amaliyot bekor qilindi. /start ni bosing.")
    return ConversationHandler.END

def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("XATOLIK: .env faylida TELEGRAM_BOT_TOKEN kiritilmagan!")
        return

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
            CallbackQueryHandler(menu_callback, pattern='^menu_')
        ],
        states={
            WAITING_FOR_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_product_name)]
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("check", lambda u, c: check_inventory_logic(u.message, c)))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern='^make_order$'))

    print("Bot ishga tushdi! Telegramdan /start yuboring.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
