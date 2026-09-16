import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from odoo_client import OdooClient

def inspect_odoo():
    client = OdooClient()
    
    print("--- Inspecting res.partner ---")
    partner = client.models.execute_kw(client.db, client.uid, client.password,
        'res.partner', 'search_read', [[]], {'limit': 1})
    if partner:
        for key in sorted(partner[0].keys()):
            if 'grade' in key or 'category' in key or 'type' in key or 'debt' in key or 'credit' in key or 'due' in key or 'A' in key or 'B' in key:
                print(f"res.partner field: {key}")
                
    print("\n--- Categories / Tags ---")
    tags = client.models.execute_kw(client.db, client.uid, client.password,
        'res.partner.category', 'search_read', [[]], {'fields': ['name']})
    print(f"Tags found: {[t['name'] for t in tags]}")

if __name__ == '__main__':
    inspect_odoo()
