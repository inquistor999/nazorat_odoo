from odoo_client import OdooClient

from image_generator import generate_receipt_image
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

def generate_receipt_image_tool(product_name: str, qty: float, location_from: str, location_to: str) -> str:
    """
    Zakaz (Intercompany transfer) tasdiqlangach, chiroyli qilib receipt/chek rasmini yaratib beradi.
    Bot rasm yarata olmagani uchun shu vositadan foydalaning!
    Sizga tovar nomi, miqdori va omborlarni berasiz. Bu sizga fayl nomini qaytaradi.
    DIQQAT: Siz o'z javobingiz oxirida [IMAGE:fayl_nomi.png] degan yozuvni qo'shishingiz shart, toki foydalanuvchiga bu rasm yetib borsin!
    """
    try:
        filename = generate_receipt_image(product_name, str(qty), location_from, location_to)
        return f"Rasm yaratildi. Iltimos, javobingizda [IMAGE:{filename}] yozuvini qo'shing."
    except Exception as e:
        return f"Rasm yaratishda xato: {e}"

# Asboblar ro'yxati (Gemini ga berish uchun)

import os

import json

import logging

from odoo_client import OdooClient



def save_learning_tool(rule: str) -> str:

    """

    Foydalanuvchi o'rgatgan yangi qoidani (masalan: 'falon vaziyatda shunday qiling') xotiraga saqlash.

    Args:

        rule: Saqlanadigan qoida matni. (Masalan: "Qachonki men bron so'rasam, faqat B2B kompaniyasida ishla, agar boshqa kompaniya kerak bo'lsa mendan ruxsat so'ra.")

    """

    try:

        from ai_agent import ai_assistant

        # Xotiraga unikal kalit bilan yozish

        import uuid

        key = f"Qoida_{uuid.uuid4().hex[:6]}"

        ai_assistant.memory[key] = rule

        ai_assistant.save_memory()

        return f"Yangi qoida muvaffaqiyatli saqlandi va men uni eslab qoldim: {rule}"

    except Exception as e:

        return f"Xatolik: {e}"



def check_product_availability_in_warehouse_tool(product_name: str, warehouse_name: str = 'B2B - 1') -> str:

    """

    Omborda tovarning erkin qoldig'ini (free_qty) tekshiradi. Bron qilishdan oldin ishlatilishi shart.

    Args:

        product_name: Tovar nomi.

        warehouse_name: Ombor nomi (Odatda 'B2B - 1').

    """

    try:

        client = OdooClient()

        # Omborni topish

        wh = client.models.execute_kw(client.db, client.uid, client.password,

            'stock.warehouse', 'search_read',

            [[('name', 'ilike', warehouse_name)]],

            {'fields': ['id', 'name', 'view_location_id'], 'limit': 1})

            

        if not wh:

            return f"Ombor topilmadi: {warehouse_name}"

            

        # Tovarni topish

        prod = client.models.execute_kw(client.db, client.uid, client.password,

            'product.product', 'search_read',

            [[('name', 'ilike', product_name)]],

            {'fields': ['id', 'name'], 'limit': 1})

            

        if not prod:

            return f"Tovar topilmadi: {product_name}"

            

        pid = prod[0]['id']

        wh_id = wh[0]['id']

        

        # Odoo 15+ da context orqali free_qty ni olish mumkin

        prod_data = client.models.execute_kw(client.db, client.uid, client.password,

            'product.product', 'read',

            [pid],

            {'fields': ['free_qty', 'qty_available'], 'context': {'warehouse': wh_id}})

            

        if prod_data:

            free_qty = prod_data[0].get('free_qty', 0.0)

            return f"Tovardan '{prod[0]['name']}' {wh[0]['name']} omborida {free_qty} erkin qoldiq bor."

        return "Qoldiq aniqlanmadi."

    except Exception as e:

        return f"Xatolik: {e}"



def create_bron_tool(client_name: str, warehouse_name: str, reason_code: str, product_name: str, qty: float, price: float) -> str:

    """

    Odoo da yangi Bron yaratadi (bron.order). Price list talab qilinmaydi, kiritilgan narx asosida hisoblanadi.

    Args:

        client_name: Mijoz ismi

        warehouse_name: Ombor nomi (masalan 'B2B - 1')

        reason_code: Bron sababi. '1' - Klient bilan gaplashib bron qo'ydim, '2' - Klient oyma-oy olgani uchun, '3' - Tovar uzilishidan qo'rqib.

        product_name: Tovar nomi

        qty: Miqdori (kg)

        price: Narxi (shunchaki son, masalan 15000)

    """

    try:

        client = OdooClient()

        

        # Mijoz

        partner = client.models.execute_kw(client.db, client.uid, client.password,

            'res.partner', 'search_read', [[('name', 'ilike', client_name)]], {'fields': ['id', 'name'], 'limit': 1})

        if not partner: return f"Xato: '{client_name}' ismli mijoz topilmadi."

        

        # Ombor

        wh = client.models.execute_kw(client.db, client.uid, client.password,

            'stock.warehouse', 'search_read', [[('name', 'ilike', warehouse_name)]], {'fields': ['id', 'name'], 'limit': 1})

        if not wh: return f"Xato: '{warehouse_name}' nomli ombor topilmadi."

        

        # Tovar

        prod = client.models.execute_kw(client.db, client.uid, client.password,

            'product.product', 'search_read', [[('name', 'ilike', product_name)]], {'fields': ['id', 'name'], 'limit': 1})

        if not prod: return f"Xato: '{product_name}' nomli tovar topilmadi."

        

        # Create Bron

        vals = {

            'partner_id': partner[0]['id'],

            'warehouse_id': wh[0]['id'],

            'reason': str(reason_code),

            'order_line_ids': [

                (0, 0, {

                    'product_id': prod[0]['id'],

                    'qty': float(qty),

                    'price_unit': float(price)

                })

            ]

        }

        

        new_bron_id = client.models.execute_kw(client.db, client.uid, client.password, 'bron.order', 'create', [vals])

        

        # Avtomatik ravishda tasdiqlaymiz (action_confirm_reserve) toki free to use darhol kamaysin
        try:
            client.models.execute_kw(client.db, client.uid, client.password, 'bron.order', 'action_confirm_reserve', [[new_bron_id]])
        except Exception as e:
            return f"Bron yaratildi, lekin tasdiqlashda xato yuz berdi (Sklad yetarli emas bo'lishi mumkin): {e}"

        return f"✅ Muvaffaqiyatli! Bron yaratildi va TASDIQLANDI (ID: {new_bron_id}). Mijoz: {partner[0]['name']}, Ombor: {wh[0]['name']}, Tovar: {prod[0]['name']} ({qty} miqdorda, {price} narxda)."

        

    except Exception as e:

        return f"Bron yaratishda xato: {e}"



def get_pending_bron_cancel_requests_tool() -> str:

    """

    O'chirishga (bekor qilishga) so'rov yuborilgan, va kutib turgan barcha bronlarni (bron.cancel.request) ro'yxatini ko'rsatadi.

    Meneger ularni tasdiqlashi uchun kerak.

    """

    try:

        client = OdooClient()

        reqs = client.models.execute_kw(client.db, client.uid, client.password,

            'bron.cancel.request', 'search_read',

            [[('state', '=', 'pending')]],

            {'fields': ['id', 'display_name', 'bron_id', 'reason', 'manager_id', 'date']})

            

        if not reqs:

            return "Ayni vaqtda kutilayotgan O'chirish so'rovlari (bron bekor qilish zaproslari) yo'q."

            

        res = "@ _   9  Kutilayotgan Bron O'chirish so'rovlari:\n"

        for r in reqs:

            res += f"- ID: {r['id']}, Bron: {r['bron_id'][1] if r.get('bron_id') else 'N/A'}, Menejer: {r['manager_id'][1] if r.get('manager_id') else 'N/A'}, Sabab: {r.get('reason', '')}, Sana: {r.get('date', '')}\n"

        return res

    except Exception as e:

        return f"Xato: {e}"



def action_bron_cancel_request_tool(request_id: int, action: str) -> str:

    """

    Kutilayotgan Bron o'chirish so'rovini tasdiqlaydi yoki rad etadi.

    Args:

        request_id: So'rov ID si (get_pending_bron_cancel_requests_tool orqali topiladi).

        action: 'approve' (tasdiqlash) yoki 'reject' (rad etish).

    """

    try:

        client = OdooClient()

        method = 'action_approve' if action == 'approve' else 'action_reject'

        client.models.execute_kw(client.db, client.uid, client.password, 'bron.cancel.request', method, [[int(request_id)]])

        return f"So'rov (ID: {request_id}) muvaffaqiyatli {'Tasdiqlandi' if action == 'approve' else 'Rad etildi'}."

    except Exception as e:

        # Agar action_approve metod yo'q bo'lsa, davlatini o'zgartiramiz

        try:

            state = 'approved' if action == 'approve' else 'rejected'

            client.models.execute_kw(client.db, client.uid, client.password, 'bron.cancel.request', 'write', [[int(request_id)], {'state': state}])

            return f"So'rov holati qo'lda '{state}' ga o'zgartirildi."

        except Exception as e2:

            return f"Tasdiqlashda xato: {e}. Qo'shimcha xato: {e2}"



odoo_tools_list = [
    get_client_debt, 
    get_product_stock, 
    get_manager_clients_count, 
    create_sale_order, 
    create_reservation,
    universal_odoo_search,
    cancel_sale_order,
    get_reservation_details_tool,
    create_intercompany_transfer_tool,
    save_learning_tool,
    check_product_availability_in_warehouse_tool,
    create_bron_tool,
    get_pending_bron_cancel_requests_tool,
    action_bron_cancel_request_tool,
    generate_receipt_image_tool,
]

def update_odoo_record(model_name: str, record_id: int, fields_to_update: dict) -> str:
    """
    Odoo bazasidagi istalgan jadvaldagi (model) ma'lumotni qisman (chistichno) tahrirlaydi.
    Masalan, bron (sale.order.line) qilingan tovar miqdorini o'zgartirish (masalan 100 kg ga tushirish) uchun 'product_uom_qty' maydoni yangilanadi.
    Args:
        model_name: Odoo modeli (masalan 'sale.order.line').
        record_id: Tahrirlanadigan ma'lumotning ID raqami.
        fields_to_update: Yangilanadigan maydonlar lyg'ati (dictionary), masalan: {'product_uom_qty': 400.0}
    Returns:
        Amal natijasi haqida ma'lumot.
    """
    try:
        from odoo_client import OdooClient
        client = OdooClient()
        success = client.models.execute_kw(client.db, client.uid, client.password,
            model_name, 'write', [[record_id], fields_to_update])
        if success:
            return f"✅ Muvaffaqiyatli! {model_name} (ID: {record_id}) dagi ma'lumotlar o'zgartirildi: {fields_to_update}"
        else:
            return f"❌ Xatolik yuz berdi. Tahrirlash amalga oshmadi."
    except Exception as e:
        return f"Xato: {e}"

def delete_odoo_record(model_name: str, record_ids: list) -> str:
    """
    Odoo bazasidagi istalgan ma'lumotni TO'LIQ o'chirib yuboradi (unlink).
    Masalan, bekor qilingan nakladnoyning hali jo'natilmagan dostavkasini (stock.picking) butunlay o'chirish uchun.
    Args:
        model_name: Odoo modeli (masalan 'stock.picking' yoki 'sale.order').
        record_ids: O'chiriladigan ID lar ro'yxati (masalan [1234]).
    Returns:
        O'chirilganligi haqida xabar.
    """
    try:
        from odoo_client import OdooClient
        client = OdooClient()
        success = client.models.execute_kw(client.db, client.uid, client.password,
            model_name, 'unlink', [record_ids])
        if success:
            return f"🚮 Muvaffaqiyatli o'chirildi! {model_name} jadvallari: {record_ids} to'liq olib tashlandi."
        else:
            return f"❌ O'chirishda xatolik yuz berdi. Ma'lumot boshqa hujjatlarga bog'langan bo'lishi mumkin."
    except Exception as e:
        return f"Xato: {e}"

def execute_odoo_button(model_name: str, method_name: str, record_ids: list) -> str:
    """
    Odoo interfeysidagi istalgan tugmani (Method) bosish imkonini beradi.
    Masalan, Nakladnoyni bekor qilish uchun 'sale.order' da 'action_cancel' methodi ishlatiladi. Bronni tasdiqlash uchun 'action_confirm' ishlatiladi.
    Args:
        model_name: Odoo modeli (masalan 'sale.order').
        method_name: Bosiladigan tugmaning backend kodi (masalan 'action_cancel', 'action_confirm').
        record_ids: Qaysi hujjatlarda (ID) shu tugma bosilishi kerak (masalan [54321]).
    Returns:
        Tugma muvaffaqiyatli bosilganligi natijasi.
    """
    try:
        from odoo_client import OdooClient
        client = OdooClient()
        client.models.execute_kw(client.db, client.uid, client.password,
            model_name, method_name, [record_ids])
        return f"🔘 '{method_name}' tugmasi {model_name} (ID: {record_ids}) uchun muvaffaqiyatli bosildi!"
    except Exception as e:
        return f"Tugma bosishda xatolik: {e}"

def execute_odoo_shell_command(python_code: str) -> str:
    """
    Odoo serverida backend (shell) orqali to'g'ridan to'g'ri Python kod ishga tushirish imkonini beradi.
    Foydalanuvchi qatiy ravishda shell orqali bajarishni va o'z tasdig'ini (Ha) berganidan so'nggina ishlatiladi.
    Odoo environment `env` o'zgaruvchisi orqali taqdim etiladi.
    Args:
        python_code: Ishga tushiriladigan Odoo Python script kodi. Bu env.cr.execute() yoki env['model'].search() bo'lishi mumkin.
    Returns:
        Scriptning bajarilish natijasi yoki print qilingan ma'lumotlar.
    """
    try:
        from odoo_client import OdooClient
        import xmlrpc.client
        client = OdooClient()
        
        # Odoo API orqali raw python ishga tushirib bo'lmaydi (xavfsizlik sababli).
        # Lekin biz buni qaysidir server action yoki base execute_kw vositasida 'ir.actions.server' orqali vaqtincha yaratib ishga tushirishimiz mumkin.
        # Bu juda ilg'or funksiya.
        
        action_vals = {
            'name': 'AI Shell Execution',
            'model_id': client.models.execute_kw(client.db, client.uid, client.password, 'ir.model', 'search', [[('model', '=', 'res.partner')]])[0],
            'state': 'code',
            'code': python_code
        }
        
        action_id = client.models.execute_kw(client.db, client.uid, client.password, 'ir.actions.server', 'create', [action_vals])
        
        result = client.models.execute_kw(client.db, client.uid, client.password, 'ir.actions.server', 'run', [[action_id]])
        
        # Tozalash
        client.models.execute_kw(client.db, client.uid, client.password, 'ir.actions.server', 'unlink', [[action_id]])
        
        return f"💻 Shell Script bajarildi. Natija: {result}"
    except Exception as e:
        return f"Shell Script Xatosi: {e}"
