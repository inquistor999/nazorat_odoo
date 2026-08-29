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

# "TORTO" so'zi bilan boshlangan barcha tovarlarni Odoo'dan ko'rish
search_words = ['TORTO', 'Muzqaymoq', 'MILSEOR', 'KAHWA', 'Shokolad Pasta', 'Razrixlitel TORTO', 'Shanti TORTO']

for word in search_words:
    results = models.execute_kw(db, uid, password,
        'product.product', 'search_read',
        [[('name', 'ilike', word), ('active', '=', True)]],
        {'fields': ['name', 'qty_available'], 'limit': 30, 'order': 'name asc'}
    )
    if results:
        print(f"\n--- '{word}' bilan bog'liq {len(results)} ta tovar ---")
        for p in results:
            print(f"  {p['name']} | Qoldiq: {p['qty_available']}")
    else:
        print(f"\n--- '{word}' uchun hech narsa topilmadi ---")
