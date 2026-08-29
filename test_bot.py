import asyncio
import datetime
import time
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.request import HTTPXRequest
import config
from analysis import create_sales_history_chart

# 3 ta test tovar
test_products = [
    {
        "name": "TORTO KAKAO (100gr) (JAMI)",
        "stock": 50,
        "monthly_sales": {'Iyun': 200, 'Iyul': 310, 'Avgust': 140},
        "reorder": "20 kg (200 sht)"
    },
    {
        "name": "Vazelin TORTO (10kg) (JAMI)",
        "stock": 20,
        "monthly_sales": {'Iyun': 400, 'Iyul': 450, 'Avgust': 500},
        "reorder": "140 kg (14 sht)"
    },
    {
        "name": "Jele PROZRACHNIY TATLI TORTO (7kg) (JAMI)",
        "stock": 10,
        "monthly_sales": {'Iyun': 100, 'Iyul': 120, 'Avgust': 130},
        "reorder": "119 kg (17 sht)"
    }
]

async def send_with_retry(send_func, retries=3, delay=3):
    """Tarmoq xatosida qayta urinish"""
    for attempt in range(retries):
        try:
            return await send_func()
        except Exception as e:
            if attempt < retries - 1:
                print(f"  Xato: {e}. {delay} soniyadan keyin qayta uriniladi...")
                await asyncio.sleep(delay)
            else:
                raise

async def send_test_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("⏳ Tahlil qilinmoqda, iltimos kuting...")

    order_list_text = []

    for p in test_products:
        name = p["name"]
        sales_90d = sum(p["monthly_sales"].values())
        daily_sales = round(sales_90d / 90, 2)
        
        months_text = "".join([f"{m} - {v} kg\n" for m, v in p["monthly_sales"].items()])
        
        msg = (
            f"⚠️ <b>Zakaz berish kerak: {name}</b>\n\n"
            f"📦 Hozirgi qoldiq: <b>{p['stock']} kg</b>\n\n"
            f"📊 <b>Oxirgi 3 oy natijasi:</b>\n"
            f"{months_text}\n"
            f"📈 O'rtacha kunlik sotuv: <b>{daily_sales} kg</b>\n\n"
            f"👉 <b>Tavsiya etiladigan zakaz miqdori: {p['reorder']}</b>"
        )
        
        chart_buf = create_sales_history_chart(name, p["monthly_sales"])
        await context.bot.send_photo(chat_id=chat_id, photo=chart_buf, caption=msg, parse_mode='HTML')
        
        order_list_text.append(f"{name} - {p['reorder']}")
        await asyncio.sleep(1) # xabarlar ketma-ket borishi uchun

    # Xotirada saqlab turamiz callback uchun
    context.user_data['order_list'] = order_list_text
    
    # Oxirida bitta button yuboramiz
    keyboard = [[InlineKeyboardButton("🛒 ZAKAZ BERISH", callback_data="make_order")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ Barcha tovarlar tahlil qilindi. Jami 4 ta tovardan zakaz berish kerak.",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "make_order":
        order_list_text = context.user_data.get('order_list', [])
        today = datetime.datetime.now().strftime("%d.%m.%Y")
        
        final_msg = f"Zakaz : {today}\n" + "\n".join(order_list_text)
        
        await query.edit_message_text(text=final_msg)

def main():
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("test", send_test_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    print("Test bot ishga tushdi. Telegramdan /test buyrug'ini yuboring.")
    application.run_polling()

if __name__ == "__main__":
    main()
