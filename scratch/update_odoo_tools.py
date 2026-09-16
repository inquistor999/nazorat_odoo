import os

file_path = "odoo_tools.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Update create_sale_order signature and logic
old_sale = '''def create_sale_order(client_name: str, product_name: str, qty: float, price: float) -> str:
    """
    Odoo'da avtomatik ravishda Sale Order (Sotuv/Nakladnoy) yaratadi. 
    A/B/C toifadagi mijozlar tekshiriladi, qarz bo'lsa sotuv bloklanadi.
    Args:
        client_name: Mijozning ismi.
        product_name: Sotilayotgan tovar nomi.
        qty: Tovar miqdori.
        price: Tovar narxi.
    Returns:
        Muvaffaqiyatli yoki xatolik haqida matnli javob.
    """
    client = OdooClient()
    return client.create_sale_order(client_name, product_name, qty, price)'''

new_sale = '''def create_sale_order(client_name: str, product_name: str, qty: float, price: float, pricelist_name: str = None) -> str:
    """
    Odoo'da avtomatik ravishda Sale Order (Sotuv/Nakladnoy) yaratadi. 
    A/B/C toifadagi mijozlar tekshiriladi, qarz bo'lsa sotuv bloklanadi.
    Args:
        client_name: Mijozning ismi.
        product_name: Sotilayotgan tovar nomi.
        qty: Tovar miqdori.
        price: Tovar narxi.
        pricelist_name: Valyuta yoki prayclist (masalan, 'Dollar', 'Sum', 'Perechesleniya').
    Returns:
        Muvaffaqiyatli yoki xatolik haqida matnli javob.
    """
    client = OdooClient()
    return client.create_sale_order(client_name, product_name, qty, price, pricelist_name)'''

content = content.replace(old_sale, new_sale)

# Update create_reservation signature and logic
old_res = '''def create_reservation(client_name: str, product_name: str, qty: float) -> str:
    """
    Mijoz uchun tovarni bron qiladi. Agar "Free to use" (Erkin qoldiq) da tovar yetsa, bron qilinadi.
    Args:
        client_name: Mijoz ismi.
        product_name: Tovar nomi.
        qty: Tovar miqdori.
    Returns:
        Muvaffaqiyatli bron qilingani yoki xatolik haqida matnli javob.
    """
    client = OdooClient()
    return client.create_reservation(client_name, product_name, qty)'''

new_res = '''def create_reservation(client_name: str, product_name: str, qty: float, pricelist_name: str = None) -> str:
    """
    Mijoz uchun tovarni bron qiladi. Agar "Free to use" (Erkin qoldiq) da tovar yetsa, bron qilinadi.
    Args:
        client_name: Mijoz ismi.
        product_name: Tovar nomi.
        qty: Tovar miqdori.
        pricelist_name: Valyuta (masalan, 'Dollar', 'Sum', 'Perechesleniya').
    Returns:
        Muvaffaqiyatli bron qilingani yoki xatolik haqida matnli javob.
    """
    client = OdooClient()
    return client.create_reservation(client_name, product_name, qty, pricelist_name)'''

content = content.replace(old_res, new_res)


new_tools = '''

def universal_odoo_search(model: str, domain: str, fields: str = None, limit: int = 10) -> str:
    """
    Odoo'dan istalgan jadval (model) bo'yicha ma'lumot qidiradi.
    Args:
        model: Odoo model nomi (masalan, 'sale.order', 'stock.picking', 'account.move').
        domain: Qidiruv sharti, Python ro'yxat string ko'rinishida (masalan, "[('state', '=', 'sale')]").
        fields: Kerakli maydonlar ro'yxati string ko'rinishida (masalan, "['name', 'amount_total']").
        limit: Maksimal natijalar soni.
    Returns:
        Qidiruv natijalari matn ko'rinishida.
    """
    import ast
    try:
        domain_list = ast.literal_eval(domain) if domain else []
        fields_list = ast.literal_eval(fields) if fields else None
        client = OdooClient()
        res = client.universal_odoo_search(model, domain_list, fields_list, limit)
        return str(res)
    except Exception as e:
        return f"Xatolik: {e}"

def cancel_sale_order(order_name: str) -> str:
    """
    Tasdiqlangan yoki qoralama nakladnoyni bekor qiladi (cancel).
    Args:
        order_name: Nakladnoyning rasmiy raqami (masalan, 'S39455').
    """
    client = OdooClient()
    return client.cancel_sale_order(order_name)

def get_reservation_details_tool(product_name: str) -> str:
    """
    Muayyan tovarning ayni vaqtda qaysi mijozlarga, qancha miqdorda va qaysi hujjat asosida bron qilinganini batafsil ko'rsatadi.
    Args:
        product_name: Tovar nomi.
    """
    client = OdooClient()
    return client.get_reservation_details(product_name)

def create_intercompany_transfer_tool(source_warehouse_id: int, dest_company_id: int, product_name: str, qty: float) -> str:
    """
    B2B dan Urikzor (ID 2) yoki Qo'qonga transfer yaratadi (Permeshsheniya).
    B2B-2 omborining id si ko'pincha 50, B2B-1 niki 47. 
    Args:
        source_warehouse_id: Ombor ID si.
        dest_company_id: Qabul qiluvchi kompaniya ID si. (Urikzor = 2).
        product_name: Tovar nomi.
        qty: Miqdor.
    """
    client = OdooClient()
    return client.create_intercompany_transfer(source_warehouse_id, dest_company_id, product_name, qty)

'''

old_list = '''# Asboblar ro'yxati (Gemini ga berish uchun)
odoo_tools_list = [get_client_debt, get_product_stock, get_manager_clients_count, create_sale_order, create_reservation]'''

new_list = '''# Asboblar ro'yxati (Gemini ga berish uchun)
odoo_tools_list = [
    get_client_debt, 
    get_product_stock, 
    get_manager_clients_count, 
    create_sale_order, 
    create_reservation,
    universal_odoo_search,
    cancel_sale_order,
    get_reservation_details_tool,
    create_intercompany_transfer_tool
]'''

content = content.replace(old_list, new_tools + new_list)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated odoo_tools.py")
