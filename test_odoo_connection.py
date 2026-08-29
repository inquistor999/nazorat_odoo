import xmlrpc.client
from dotenv import load_dotenv
import os
import sys

# Windows konsol uchun UTF-8 majburlash
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

url = os.getenv("ODOO_URL")
db = os.getenv("ODOO_DB")
username = os.getenv("ODOO_USERNAME")
password = os.getenv("ODOO_PASSWORD")

print(f"Ulanish sinab korilmoqda...")
print(f"URL  : {url}")
print(f"DB   : {db}")
print(f"User : {username}")
print()

try:
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    
    version = common.version()
    print(f"[OK] Server bilan aloqa ornatildi! Odoo versiyasi: {version['server_version']}")
    
    uid = common.authenticate(db, username, password, {})
    
    if uid:
        print(f"[OK] Login muvaffaqiyatli! Foydalanuvchi ID: {uid}")
        
        models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
        products = models.execute_kw(db, uid, password,
            'product.product', 'search_read',
            [[('active', '=', True)]],
            {'fields': ['name', 'qty_available'], 'limit': 5}
        )
        
        print(f"\n[OK] Odoo'da {len(products)} ta tovar topildi (namuna):")
        for p in products:
            print(f"   - {p['name']} | Qoldiq: {p['qty_available']}")
    else:
        print("[XATO] Login xato! Username yoki parol notogri.")

except Exception as e:
    print(f"[XATO] : {e}")
    print("\nEhtimoliy sabablar:")
    print("  - URL notogri yoki bazaning nomi xato")
    print("  - Internet aloqa yoq")
    print("  - Odoo serveri yoqilmagan")

