import sys
import os
from datetime import datetime, timedelta

# Add parent dir to path so we can import odoo_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from odoo_client import OdooClient

def get_odoo_info():
    client = OdooClient()
    
    print("--- Odoo Ma'lumotlari ---")
    
    # 1. Barcha modullar (o'rnatilgan)
    modules = client.models.execute_kw(client.db, client.uid, client.password, 
        'ir.module.module', 'search_count', [[('state', '=', 'installed')]])
    print(f"O'rnatilgan modullar soni: {modules}")
    
    # 2. Xodimlar (Sotuvchilar / Menenjerlar) - res.users
    users = client.models.execute_kw(client.db, client.uid, client.password,
        'res.users', 'search_read', [[('share', '=', False)]], {'fields': ['name', 'login']})
    print(f"\nJami xodimlar / menejerlar (ichki foydalanuvchilar): {len(users)}")
    for u in users:
        print(f" - {u['name']} ({u['login']})")
        
    # 3. Kontaktlar (Mijozlar va Hamkorlar) - res.partner
    contacts = client.models.execute_kw(client.db, client.uid, client.password,
        'res.partner', 'search_count', [[]])
    print(f"\nUmumiy kontaktlar (mijozlar/hamkorlar) soni: {contacts}")
    
    # 4. Tovar va mahsulotlar soni
    products = client.models.execute_kw(client.db, client.uid, client.password,
        'product.product', 'search_count', [[]])
    print(f"Jami tovarlar/mahsulotlar soni: {products}")
    
    # 5. Oxirgi 1 oylik savdo (Sales Orders)
    one_month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    try:
        sales = client.models.execute_kw(client.db, client.uid, client.password,
            'sale.order', 'search_read', 
            [[('state', 'in', ['sale', 'done']), ('date_order', '>=', one_month_ago)]],
            {'fields': ['amount_total']})
        
        total_sales_sum = sum(s['amount_total'] for s in sales)
        print(f"\nOxirgi 30 kunlik tasdiqlangan savdolar (Sale Orders) soni: {len(sales)}")
        print(f"Oxirgi 30 kunlik savdo aylanmasi (summa): {total_sales_sum:,.2f}")
    except Exception as e:
        print(f"\nSavdolarni olishda xato (balki sale moduli yo'qdir): {e}")

if __name__ == '__main__':
    get_odoo_info()
