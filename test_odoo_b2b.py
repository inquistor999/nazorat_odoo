"""
B2B filtrini to'liq tekshirish
"""
from odoo_client import OdooClient

def main():
    odoo = OdooClient()
    
    # tracked_products.txt dan birinchi 3 ta JAMI tovarni test qilamiz
    test_names = [
        "Glazur KLUBNIKA KEKSAN (7kg) (JAMI)",
        "Jele KARAMELNIY KEKSAN (7kg) (JAMI)",
        "Jele KLUBNICHNIY KEKSAN (7kg) (JAMI)",
    ]
    
    for name in test_names:
        print(f"\n{'='*55}")
        print(f"Tovar: {name}")
        
        product = odoo.get_product_info_by_name(name)
        if not product:
            print("  ❌ Topilmadi!")
            continue
        
        pid = product['id']
        b2b_qty = product['qty_available']
        print(f"  OK: ID={pid}, B2B qoldiq={b2b_qty} kg")
        
        monthly = odoo.get_monthly_sales(pid, num_months=3)
        print(f"  Oylik sotuvlar (3 oy): {monthly}")
        
        total_90d = odoo.get_sales_total_90d(pid)
        print(f"  90 kunlik jami: {total_90d} kg")
        
        stats = odoo.get_sales_statistics(pid, num_months=5)
        print(f"  Menenjerlar: {stats['manager_sales']}")
        print(f"  Narx: min={stats['min_price']}, max={stats['max_price']}")
        
        purchase = odoo.get_last_purchase(pid)
        print(f"  Oxirgi prixod: {purchase}")

if __name__ == '__main__':
    main()
