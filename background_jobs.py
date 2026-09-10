import json
import os
from datetime import datetime, timedelta
import logging
from telegram.ext import ContextTypes
import config
from odoo_client import OdooClient

ALERTS_FILE = 'alerts_memory.json'

def load_alerts_memory():
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {'overdue_partners': {}, 'notified_sales': []}
    return {'overdue_partners': {}, 'notified_sales': [], 'notified_pickings': []}

def save_alerts_memory(memory):
    with open(ALERTS_FILE, 'w') as f:
        json.dump(memory, f)

async def run_monitoring_jobs(context: ContextTypes.DEFAULT_TYPE):
    """
    Har 10 daqiqada aylanuvchi asosiy monitoring funksiyasi.
    """
    admin_id = getattr(config, 'ADMIN_CHAT_ID', None)
    if not admin_id:
        logging.warning("ADMIN_CHAT_ID config faylida topilmadi. Xabarlar yuborilmaydi.")
        return
        
    client = OdooClient()
    memory = load_alerts_memory()
    if 'notified_pickings' not in memory:
        memory['notified_pickings'] = []
        
    ten_mins_ago = (datetime.now() - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    alerts_to_send = []
    
    # 1. Sebestoimost nazorati (Tannarxdan arzon sotuv)
    try:
        recent_sales = client.models.execute_kw(client.db, client.uid, client.password,
            'sale.order', 'search_read',
            [[('date_order', '>=', ten_mins_ago), ('state', 'in', ['sale', 'done'])]],
            {'fields': ['id', 'name', 'partner_id', 'order_line']})
            
        for sale in recent_sales:
            sale_id = sale['id']
            if sale_id in memory['notified_sales']:
                continue
                
            lines = client.models.execute_kw(client.db, client.uid, client.password,
                'sale.order.line', 'read',
                [sale['order_line']],
                {'fields': ['product_id', 'price_unit', 'purchase_price', 'product_uom_qty']})
                
            below_cost_lines = []
            for line in lines:
                price = line.get('price_unit', 0)
                cost = line.get('purchase_price', 0)
                if price < cost and price > 0: # 0 narxlilar sovg'a bo'lishi mumkin
                    product_name = line['product_id'][1] if line.get('product_id') else 'Noma\'lum'
                    below_cost_lines.append(f" - {product_name}: Sotildi {price}$, Tannarx {cost}$")
            
            if below_cost_lines:
                alert_msg = f"🚨 **ZARARGA SOTUV DIQQATI!**\nNakladnoy: {sale['name']}\nMijoz: {sale['partner_id'][1]}\n\nTovarlar:\n" + "\n".join(below_cost_lines)
                alerts_to_send.append(alert_msg)
                memory['notified_sales'].append(sale_id)
    except Exception as e:
        logging.error(f"Sebestoimost tekshirishda xato: {e}")

    # 2. B va C toifadagi qarzdorliklar nazorati
    try:
        partners = client.models.execute_kw(client.db, client.uid, client.password,
            'res.partner', 'search_read',
            [[('x_studio_category', 'in', ['B', 'C']), ('total_overdue', '>', 10)]],
            {'fields': ['id', 'name', 'x_studio_category', 'total_overdue']})
            
        for p in partners:
            pid = str(p['id'])
            overdue = p['total_overdue']
            
            # Agar qarz avvalgisidan kamida 10$ ga oshgan bo'lsa yoki birinchi marta bo'lsa
            last_overdue = memory['overdue_partners'].get(pid, 0)
            if overdue > last_overdue + 10:
                alert_msg = f"⚠️ **QARZDORLIK OSHDI!**\nMijoz: {p['name']} ({p['x_studio_category']} toifa)\nMuddati o'tgan qarz: {overdue:,.2f} $\n(Oldingi holat: {last_overdue:,.2f} $)"
                alerts_to_send.append(alert_msg)
                memory['overdue_partners'][pid] = overdue
    except Exception as e:
        logging.error(f"Qarzdorlik tekshirishda xato: {e}")
        
    # 3. Yangi Kelgan Tovar (Prixod - Intercompany Transfers)
    try:
        pickings = client.models.execute_kw(client.db, client.uid, client.password,
            'stock.picking', 'search_read',
            [[('create_date', '>=', ten_mins_ago), ('picking_type_code', '=', 'internal')]],
            {'fields': ['id', 'name', 'location_id', 'location_dest_id']})
            
        for pick in pickings:
            pick_id = pick['id']
            if pick_id in memory['notified_pickings']:
                continue
                
            loc_from = pick['location_id'][1] if pick.get('location_id') else ''
            loc_to = pick['location_dest_id'][1] if pick.get('location_dest_id') else ''
            
            if 'Citric' in loc_from and 'B2B' in loc_to:
                alert_msg = f"📦 **YANGI PRIXOD (Citric -> B2B)!**\nHujjat: {pick['name']}\nYangi tovarlar B2B omboriga yo'lga chiqdi yoki qabul qilindi."
                alerts_to_send.append(alert_msg)
            
            memory['notified_pickings'].append(pick_id)
    except Exception as e:
        logging.error(f"Prixod tekshirishda xato: {e}")

    # Xotirani saqlash va xabarlarni yuborish
    save_alerts_memory(memory)
    
    for alert in alerts_to_send:
        try:
            await context.bot.send_message(chat_id=admin_id, text=alert, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Admin guruhiga xabar yuborishda xato: {e}")
