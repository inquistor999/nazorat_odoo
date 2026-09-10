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

# Asboblar ro'yxati (Gemini ga berish uchun)
odoo_tools_list = [get_client_debt, get_product_stock, get_manager_clients_count]
