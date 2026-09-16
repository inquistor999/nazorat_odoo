import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from odoo_client import OdooClient

def inspect_creation():
    client = OdooClient()
    
    print("--- Testing Models ---")
    partner = client.models.execute_kw(client.db, client.uid, client.password,
        'res.partner', 'search_read', [[]], {'limit': 1, 'fields': ['id', 'name']})
        
    product = client.models.execute_kw(client.db, client.uid, client.password,
        'product.product', 'search_read', [[]], {'limit': 1, 'fields': ['id', 'name']})
        
    print(f"Partner: {partner[0] if partner else None}")
    print(f"Product: {product[0] if product else None}")

if __name__ == '__main__':
    inspect_creation()
