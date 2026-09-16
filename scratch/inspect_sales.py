import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from odoo_client import OdooClient

def inspect_sales():
    client = OdooClient()
    
    print("--- Inspecting sale.order.line ---")
    lines = client.models.execute_kw(client.db, client.uid, client.password,
        'sale.order.line', 'search_read', [[]], {'limit': 1})
    if lines:
        for key in sorted(lines[0].keys()):
            if 'price' in key or 'cost' in key or 'purchase' in key or 'standard' in key or 'margin' in key:
                print(f"sale.order.line field: {key}")
                
    print("--- Inspecting stock.picking ---")
    pickings = client.models.execute_kw(client.db, client.uid, client.password,
        'stock.picking', 'search_read', [[]], {'limit': 1})
    if pickings:
        for key in sorted(pickings[0].keys()):
            if 'type' in key or 'location' in key or 'company' in key:
                print(f"stock.picking field: {key}")

if __name__ == '__main__':
    inspect_sales()
