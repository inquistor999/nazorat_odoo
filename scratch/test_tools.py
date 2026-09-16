import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from odoo_client import OdooClient

def test_client_debt(client_name):
    client = OdooClient()
    partner = client.models.execute_kw(client.db, client.uid, client.password,
        'res.partner', 'search_read', 
        [[('name', 'ilike', client_name)]], 
        {'fields': ['name', 'credit', 'total_due', 'total_overdue', 'x_studio_category', 'category_id'], 'limit': 1})
    
    if partner:
        p = partner[0]
        print(f"Mijoz: {p['name']}")
        print(f"Qarzi: {p.get('credit', 0)}")
        print(f"Total due: {p.get('total_due', 0)}")
        print(f"Muddati o'tgan: {p.get('total_overdue', 0)}")
        print(f"Kategoriya (studio): {p.get('x_studio_category')}")
        print(f"Teglar: {p.get('category_id')}")
    else:
        print("Mijoz topilmadi")

if __name__ == '__main__':
    test_client_debt("Akmal")
