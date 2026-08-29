import xmlrpc.client
from dotenv import load_dotenv
import os, sys

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

url = os.getenv("ODOO_URL")
db = os.getenv("ODOO_DB")
username = os.getenv("ODOO_USERNAME")
password = os.getenv("ODOO_PASSWORD")

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# 1. Kompaniyalar royxati
print("=" * 60)
print("KOMPANIYALAR:")
print("=" * 60)
companies = models.execute_kw(db, uid, password,
    'res.company', 'search_read',
    [[]],
    {'fields': ['id', 'name']}
)
for c in companies:
    print(f"  ID: {c['id']} | Nomi: {c['name']}")

# 2. Skladlar (warehouse)
print("\n" + "=" * 60)
print("SKLADLAR (WAREHOUSE):")
print("=" * 60)
warehouses = models.execute_kw(db, uid, password,
    'stock.warehouse', 'search_read',
    [[]],
    {'fields': ['id', 'name', 'company_id', 'lot_stock_id']}
)
for w in warehouses:
    print(f"  ID: {w['id']} | Nomi: {w['name']} | Kompaniya: {w['company_id']} | Stock Location ID: {w['lot_stock_id']}")

# 3. Asosiy stock location lar
print("\n" + "=" * 60)
print("STOCK LOCATIONS:")
print("=" * 60)
locations = models.execute_kw(db, uid, password,
    'stock.location', 'search_read',
    [[('usage', '=', 'internal')]],
    {'fields': ['id', 'name', 'complete_name', 'company_id']}
)
for loc in locations:
    print(f"  ID: {loc['id']} | Nomi: {loc['complete_name']} | Kompaniya: {loc['company_id']}")

# 4. Bitta test tovar uchun quant tekshirish
print("\n" + "=" * 60)
print("TEST: 'Jele KARAMELNIY KEKSAN (7kg) (JAMI)' UCHUN STOCK QUANT:")
print("=" * 60)
test_product = models.execute_kw(db, uid, password,
    'product.product', 'search_read',
    [[('name', '=', 'Jele KARAMELNIY KEKSAN (7kg) (JAMI)')]],
    {'fields': ['id', 'name'], 'limit': 1}
)
if test_product:
    pid = test_product[0]['id']
    quants = models.execute_kw(db, uid, password,
        'stock.quant', 'search_read',
        [[('product_id', '=', pid), ('location_id.usage', '=', 'internal')]],
        {'fields': ['product_id', 'quantity', 'location_id', 'company_id']}
    )
    for q in quants:
        print(f"  Miqdor: {q['quantity']} | Location: {q['location_id']} | Kompaniya: {q['company_id']}")
