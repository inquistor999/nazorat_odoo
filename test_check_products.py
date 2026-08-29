import xmlrpc.client
from dotenv import load_dotenv
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

url = os.getenv("ODOO_URL")
db = os.getenv("ODOO_DB")
username = os.getenv("ODOO_USERNAME")
password = os.getenv("ODOO_PASSWORD")

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# tracked_products.txt dan nomlarni o'qish
with open('tracked_products.txt', 'r', encoding='utf-8') as f:
    tracked = [line.strip() for line in f if line.strip()]

print(f"Jami kuzatiladigan tovarlar soni: {len(tracked)}\n")
print("=" * 60)

found = []
not_found = []

for name in tracked:
    results = models.execute_kw(db, uid, password,
        'product.product', 'search_read',
        [[('name', '=', name), ('active', '=', True)]],
        {'fields': ['name', 'qty_available'], 'limit': 1}
    )
    if results:
        p = results[0]
        found.append(name)
        print(f"[TOPILDI]   {p['name']} | Qoldiq: {p['qty_available']}")
    else:
        not_found.append(name)
        print(f"[TOPILMADI] {name}")

print("=" * 60)
print(f"\nNatija: {len(found)} ta topildi, {len(not_found)} ta topilmadi.")

if not_found:
    print("\nTopilmagan tovarlar:")
    for n in not_found:
        print(f"  - {n}")
