import os
import re

file_path = "odoo_client.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace create_sale_order signature and logic
old_sale = '''    def create_sale_order(self, client_name: str, product_name: str, qty: float, price: float) -> str:'''
new_sale = '''    def create_sale_order(self, client_name: str, product_name: str, qty: float, price: float, pricelist_name: str = None) -> str:'''

content = content.replace(old_sale, new_sale)

old_sale_logic = '''            sale_id = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'create', [{'partner_id': p['id']}])
                
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order.line', 'create', [{
                    'order_id': sale_id,
                    'product_id': pr['id'],
                    'product_uom_qty': qty_f,
                    'price_unit': price_f
                }])
                
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'action_confirm', [[sale_id]])
                
            return f"✅ Muvaffaqiyatli! {p['name']} ga {qty_f} ta {pr['name']} sotildi va tasdiqlandi. (Nakladnoy ID: {sale_id})"'''

new_sale_logic = '''            sale_vals = {'partner_id': p['id']}
            if pricelist_name:
                pricelist = self.models.execute_kw(self.db, self.uid, self.password,
                    'product.pricelist', 'search_read',
                    [[('name', 'ilike', pricelist_name)]],
                    {'limit': 1, 'fields': ['id', 'name']})
                if pricelist:
                    sale_vals['pricelist_id'] = pricelist[0]['id']
            
            sale_id = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'create', [sale_vals])
                
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order.line', 'create', [{
                    'order_id': sale_id,
                    'product_id': pr['id'],
                    'product_uom_qty': qty_f,
                    'price_unit': price_f
                }])
                
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'action_confirm', [[sale_id]])
                
            # Haqiqiy nomini (S-xxxx) o'qib olish
            sale = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'search_read',
                [[('id', '=', sale_id)]],
                {'limit': 1, 'fields': ['name']})
            sale_name = sale[0]['name'] if sale else str(sale_id)
                
            return f"✅ Muvaffaqiyatli! {p['name']} ga {qty_f} ta {pr['name']} sotildi va tasdiqlandi. (Nakladnoy raqami: {sale_name})"'''

content = content.replace(old_sale_logic, new_sale_logic)

# Replace create_reservation signature and logic similarly
old_res = '''    def create_reservation(self, client_name: str, product_name: str, qty: float) -> str:'''
new_res = '''    def create_reservation(self, client_name: str, product_name: str, qty: float, pricelist_name: str = None) -> str:'''

content = content.replace(old_res, new_res)

old_res_logic = '''            sale_id = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'create', [{'partner_id': p['id']}])
                
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order.line', 'create', [{
                    'order_id': sale_id,
                    'product_id': pr['id'],
                    'product_uom_qty': qty_f,
                    'price_unit': pr.get('lst_price', 0)
                }])
                
            # Bron uchun confirm qilamiz, toki tovar free to use dan olib tashlansin
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'action_confirm', [[sale_id]])
                
            return f"🛡 Muvaffaqiyatli! {qty_f} ta {pr['name']} tovari {p['name']} uchun bron qilindi (Sotuv ID: {sale_id})."'''

new_res_logic = '''            sale_vals = {'partner_id': p['id']}
            if pricelist_name:
                pricelist = self.models.execute_kw(self.db, self.uid, self.password,
                    'product.pricelist', 'search_read',
                    [[('name', 'ilike', pricelist_name)]],
                    {'limit': 1, 'fields': ['id', 'name']})
                if pricelist:
                    sale_vals['pricelist_id'] = pricelist[0]['id']
            
            sale_id = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'create', [sale_vals])
                
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order.line', 'create', [{
                    'order_id': sale_id,
                    'product_id': pr['id'],
                    'product_uom_qty': qty_f,
                    'price_unit': pr.get('lst_price', 0)
                }])
                
            # Bron uchun confirm qilamiz, toki tovar free to use dan olib tashlansin
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'action_confirm', [[sale_id]])
                
            sale = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'search_read',
                [[('id', '=', sale_id)]],
                {'limit': 1, 'fields': ['name']})
            sale_name = sale[0]['name'] if sale else str(sale_id)
                
            return f"🛡 Muvaffaqiyatli! {qty_f} ta {pr['name']} tovari {p['name']} uchun bron qilindi (Sotuv raqami: {sale_name})."'''

content = content.replace(old_res_logic, new_res_logic)

# Adding new methods at the end of class
new_methods = '''
    def universal_odoo_search(self, model: str, domain: list, fields: list = None, limit: int = 10) -> list:
        """
        Universal qidiruv metodi.
        """
        try:
            kwargs = {'limit': limit}
            if fields:
                kwargs['fields'] = fields
            return self.models.execute_kw(self.db, self.uid, self.password, model, 'search_read', [domain], kwargs)
        except Exception as e:
            return [{"error": str(e)}]

    def cancel_sale_order(self, order_name: str) -> str:
        """S-xxxx raqamli nakladnoyni ochirib yuborish (cancel)."""
        try:
            orders = self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'search_read',
                [[('name', '=', order_name)]],
                {'limit': 1, 'fields': ['id', 'state']})
            if not orders:
                return f"Xato: '{order_name}' raqamli nakladnoy topilmadi."
            
            order_id = orders[0]['id']
            state = orders[0]['state']
            if state == 'cancel':
                return f"{order_name} allaqachon bekor qilingan."
            
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'action_cancel', [[order_id]])
            return f"✅ {order_name} nakladnoy muvaffaqiyatli bekor qilindi (cancel)."
        except Exception as e:
            return f"Xato: {e}"

    def get_reservation_details(self, product_name: str) -> str:
        """Muayyan tovar qancha va kimlar tomonidan bron qilinganini batafsil ko'rsatadi."""
        try:
            product = self._find_product(product_name)
            if not product:
                return f"Xato: '{product_name}' topilmadi."
            
            pid = product['id']
            # stock.move da 'assigned' holatdagi, chiqib ketmagan qatorlarni izlash
            moves = self.models.execute_kw(self.db, self.uid, self.password,
                'stock.move', 'search_read',
                [[('product_id', '=', pid), ('state', 'in', ['assigned', 'partially_available'])]],
                {'fields': ['picking_id', 'product_uom_qty', 'reserved_availability', 'origin', 'partner_id']})
            
            if not moves:
                return f"'{product_name}' bo'yicha aktiv bronlar topilmadi."
            
            res = [f"📦 **{product['name']}** uchun faol bronlar:"]
            total_res = 0
            for m in moves:
                qty = m.get('reserved_availability', 0)
                if qty <= 0:
                    continue
                total_res += qty
                partner = m.get('partner_id')
                p_name = partner[1] if partner else "Noma'lum"
                origin = m.get('origin', "Noma'lum hujjat")
                res.append(f"- Mijoz: {p_name} | Miqdor: {qty} | Hujjat: {origin}")
            
            res.append(f"**Jami bron:** {total_res}")
            return "\\n".join(res)
        except Exception as e:
            return f"Xato: {e}"

    def create_intercompany_transfer(self, source_warehouse_id: int, dest_company_id: int, product_name: str, qty: float) -> str:
        """
        B2B dan Urikzor/Qo'qonga intercompany transfer yaratadi.
        Hozircha Draft holatida saqlaymiz, tasdiqlash u yoq bu yoq keyin qilinadi (yoki LLM keyinroq action_confirm qiladi).
        """
        try:
            qty_f = float(qty)
            product = self._find_product(product_name)
            if not product:
                return f"Xato: '{product_name}' topilmadi."
            
            pid = product['id']
            
            # Transfer yozuvi
            vals = {
                'company_from_id': B2B_COMPANY_ID,
                'warehouse_from_id': source_warehouse_id,
                'company_to_id': dest_company_id,
                'state': 'draft' # Boshida draft qilib yaratamiz
            }
            transfer_id = self.models.execute_kw(self.db, self.uid, self.password,
                'intercompany.transfer', 'create', [vals])
            
            # Line yaratish
            line_vals = {
                'transfer_id': transfer_id,
                'product_id': pid,
                'quantity': qty_f
            }
            self.models.execute_kw(self.db, self.uid, self.password,
                'intercompany.transfer.line', 'create', [line_vals])
            
            # return the ID so AI can confirm or generate link
            return f"✅ Muvaffaqiyatli yaratildi. Transfer ID: {transfer_id} (Holat: Draft). Tasdiqlash kerak."
        except Exception as e:
            return f"Xato: {e}"
'''

content += new_methods

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated odoo_client.py")
