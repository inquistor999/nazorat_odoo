from odoo_client import OdooClient

def get_client_debt(client_name: str) -> str:
    """
    Odoo bazasidan mijozning (klientning) umumiy qarzdorligi, muddati o'tgan qarzi va uning toifasini (A, B, C) olib beradi.
    Args:
        client_name: Mijozning ismi yoki kompaniya nomi.
    Returns:
        Mijoz qarzdorligi haqida qisqacha ma'lumot (matn ko'rinishida).
    """
    try:
        client = OdooClient()
        partner = client.models.execute_kw(client.db, client.uid, client.password,
            'res.partner', 'search_read', 
            [[('name', 'ilike', client_name)]], 
            {'fields': ['name', 'credit', 'total_due', 'total_overdue', 'x_studio_category'], 'limit': 1})
        
        if partner:
            p = partner[0]
            name = p.get('name', '')
            total_due = p.get('total_due', 0)
            overdue = p.get('total_overdue', 0)
            category = p.get('x_studio_category', 'Noma\'lum')
            
            result = f"Mijoz: {name}\n"
            result += f"Umumiy qarzdorlik: {total_due:,.2f} $\n"
            result += f"Muddati o'tgan qarz (prosrochka): {overdue:,.2f} $\n"
            result += f"Kategoriyasi: {category}\n"
            return result
        else:
            return f"Kechirasiz, '{client_name}' ismli mijoz bazadan topilmadi."
    except Exception as e:
        return f"Xatolik yuz berdi: {e}"

def get_product_stock(product_name: str) -> str:
    """
    Odoo bazasidan tovarning qoldig'ini (omborda qancha borligi) va erkin (bron qilinmagan) qismini aniqlab beradi.
    Args:
        product_name: Tovarning nomi.
    Returns:
        Tovar qoldig'i haqida ma'lumot.
    """
    try:
        client = OdooClient()
        # Find product
        product = client.models.execute_kw(client.db, client.uid, client.password,
            'product.product', 'search_read', 
            [[('name', 'ilike', product_name)]], 
            {'fields': ['id', 'name', 'qty_available', 'virtual_available'], 'limit': 1})
            
        if product:
            p = product[0]
            name = p.get('name', '')
            qty = p.get('qty_available', 0) # Qolda bor
            free_qty = p.get('virtual_available', 0) # Erkin qoldiq (bron qilinganlar chegirilgan)
            reserved = qty - free_qty
            
            result = f"Tovar: {name}\n"
            result += f"Haqiqiy qoldiq (Skladda): {qty:,.2f}\n"
            result += f"Bron qilingan (Birovga atalgan): {reserved:,.2f}\n"
            result += f"Erkin sotuvga bor (Free to use): {free_qty:,.2f}\n"
            return result
        else:
            return f"Kechirasiz, '{product_name}' nomli tovar topilmadi."
    except Exception as e:
        return f"Xatolik yuz berdi: {e}"

def get_manager_clients_count(manager_name: str) -> str:
    """
    Odoo bazasidan qaysi menejerda nechta mijoz borligini aniqlab beradi.
    Args:
        manager_name: Menejerning ismi (masalan 'Behzod' yoki 'Samandar').
    Returns:
        Menejerga biriktirilgan mijozlar soni.
    """
    try:
        client = OdooClient()
        # Find user first
        user = client.models.execute_kw(client.db, client.uid, client.password,
            'res.users', 'search_read', 
            [[('name', 'ilike', manager_name)]], 
            {'fields': ['id', 'name'], 'limit': 1})
            
        if user:
            u = user[0]
            uid = u['id']
            # Find contacts assigned to this user
            count = client.models.execute_kw(client.db, client.uid, client.password,
                'res.partner', 'search_count', 
                [[('user_id', '=', uid)]])
                
            return f"Menejer {u['name']} ga jami {count} ta mijoz biriktirilgan."
        else:
            return f"Kechirasiz, '{manager_name}' ismli menejer topilmadi."
    except Exception as e:
        return f"Xatolik yuz berdi: {e}"

def create_sale_order(client_name: str, product_name: str, qty: float, price: float, pricelist_name: str = None) -> str:
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
    return client.create_sale_order(client_name, product_name, qty, price, pricelist_name)

def create_reservation(client_name: str, product_name: str, qty: float, pricelist_name: str = None) -> str:
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
    return client.create_reservation(client_name, product_name, qty, pricelist_name)



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

# Asboblar ro'yxati (Gemini ga berish uchun)
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
]
