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
        return f"✅ Muvaffaqiyatli! Bron yaratildi (ID: {new_bron_id}). Mijoz: {partner[0]['name']}, Ombor: {wh[0]['name']}, Tovar: {prod[0]['name']} ({qty} miqdorda, {price} narxda)."
        
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
            
        res = "📋 Kutilayotgan Bron O'chirish so'rovlari:\n"
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
