import xmlrpc.client
import config
from datetime import datetime, timedelta

# B2B kompaniyasi ID
B2B_COMPANY_ID = 3

# B2B ichki ombor joylari ID lari
B2B_LOC_IDS = [47, 50, 52, 53, 79, 82, 86]

def _clean_product_name(name):
    """Mahsulot nomidan ' (JAMI)' suffixini olib tashlaydi (Odoo da bu yozilmagan)"""
    return name.replace(' (JAMI)', '').strip()


class OdooClient:
    def __init__(self):
        self.url = config.ODOO_URL
        self.db = config.ODOO_DB
        self.username = config.ODOO_USERNAME
        self.password = config.ODOO_PASSWORD
        
        self.common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
        self.uid = self.common.authenticate(self.db, self.username, self.password, {})
        self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')

    def _exec(self, model, method, domain, fields, **kwargs):
        """Qisqartirilgan execute_kw chaqiruvi"""
        return self.models.execute_kw(
            self.db, self.uid, self.password,
            model, method, [domain], {'fields': fields, **kwargs}
        )

    def _find_product(self, name):
        """Mahsulotni qidirish: 1) to'liq nom, 2) (JAMI) siz, 3) so'zlarga bo'lib aqlli qidiruv"""
        # 1-urinish: to'liq nom
        result = self._exec('product.product', 'search_read',
            [('name', '=', name)], ['id', 'name', 'uom_id'], limit=1)
        if result:
            return result[0]
        
        # 2-urinish: ' (JAMI)' ni olib tashlab
        clean = name.replace(' (JAMI)', '').strip()
        if clean != name:
            result = self._exec('product.product', 'search_read',
                [('name', '=', clean)], ['id', 'name', 'uom_id'], limit=1)
            if result:
                return result[0]
        
        # 3-urinish: so'zlarga bo'lib qidirish (fuzzy search)
        words = [w for w in clean.split() if w]
        domain = []
        for word in words:
            domain.append(('name', 'ilike', word))
            
        result = self._exec('product.product', 'search_read',
            domain, ['id', 'name', 'uom_id'], limit=1)
        return result[0] if result else None

    def get_product_info_by_name(self, product_name):
        """
        Universal mahsulot qidirish.
        - To'liq nom bilan birinchi urinadi
        - Topilmasa '(JAMI)' ni olib tashlab qidiradi
        - Oxirida ilike bilan qidiradi
        - Hozirgi qoldiq faqat B2B omborlaridan (stock.quant)
        """
        product = self._find_product(product_name)
        if not product:
            return None
        
        pid = product['id']
        
        # B2B omborlaridagi haqiqiy qoldiqni olish
        quants = self._exec('stock.quant', 'search_read',
            [('product_id', '=', pid), ('location_id', 'in', B2B_LOC_IDS)],
            ['quantity']
        )
        b2b_qty = round(sum(q['quantity'] for q in quants if q['quantity'] > 0), 2)
        
        return {
            'id': pid,
            'name': product['name'],
            'qty_available': b2b_qty,
            'uom_id': product.get('uom_id'),
        }

    def search_products(self, query, limit=10):
        """
        Foydalanuvchi kiritgan so'zlar bo'yicha aqlli qidiruv (fuzzy search).
        Masalan 'jele vanil torto' kiritilsa, shu uchala so'z qatnashgan barcha tovarlarni topadi.
        """
        query = query.replace('(JAMI)', '').strip()
        words = [w for w in query.split() if w]
        
        domain = []
        for word in words:
            domain.append(('name', 'ilike', word))
            
        results = self._exec('product.product', 'search_read', 
                             domain, ['id', 'name', 'uom_id'], limit=limit)
        return results

    def _get_sale_order_qty(self, product_id, date_from, date_to=None):
        """
        B2B prodajasidagi faqat aktiv zakazlardan sotuv miqdori.
        Bekor qilingan (cancel) va loyiha (draft) holatdagilar OLINMAYDI.
        """
        domain = [
            ('product_id', '=', product_id),
            ('state', 'in', ['sale', 'done']),          # faqat tasdiqlangan va yakunlangan
            ('order_id.company_id', '=', B2B_COMPANY_ID),
            ('order_id.date_order', '>=', date_from.strftime('%Y-%m-%d 00:00:00')),
        ]
        if date_to:
            domain.append(('order_id.date_order', '<', date_to.strftime('%Y-%m-%d 00:00:00')))
        
        order_lines = self._exec('sale.order.line', 'search_read',
            domain, ['product_uom_qty']
        )
        return round(sum(line['product_uom_qty'] for line in order_lines), 2)

    def _get_intercompany_transfer_qty(self, product_id, date_from, date_to=None):
        """
        Intercompany transfer orqali B2B omboridan chiqgan tovar miqdori.
        B2B -> Urikzor yoki B2B -> Qo'qon (bajarilgan transferlar).
        """
        domain = [
            ('company_from_id', '=', 3),  # B2B
            ('state', '=', 'done'),
            ('scheduled_date', '>=', date_from.strftime('%Y-%m-%d 00:00:00')),
        ]
        if date_to:
            domain.append(('scheduled_date', '<', date_to.strftime('%Y-%m-%d 00:00:00')))
            
        transfers = self._exec('intercompany.transfer', 'search_read', domain, ['id'])
        if not transfers:
            return 0.0
            
        transfer_ids = [t['id'] for t in transfers]
        
        line_domain = [
            ('transfer_id', 'in', transfer_ids),
            ('product_id', '=', product_id)
        ]
        
        lines = self._exec('intercompany.transfer.line', 'search_read', line_domain, ['quantity'])
        
        total = sum(line.get('quantity', 0) for line in lines)
        return round(total, 2)

    def get_monthly_sales(self, product_id, num_months=3):
        """Oxirgi N oy uchun B2B sotuvlari: prodaja + intercompany transfer"""
        monthly_sales = {}
        now = datetime.now()

        month_names_uz = {
            1: 'Yanvar', 2: 'Fevral', 3: 'Mart', 4: 'Aprel',
            5: 'May', 6: 'Iyun', 7: 'Iyul', 8: 'Avgust',
            9: 'Sentabr', 10: 'Oktabr', 11: 'Noyabr', 12: 'Dekabr'
        }

        for i in range(num_months - 1, -1, -1):
            month_offset = now.month - i
            year_offset = now.year
            while month_offset <= 0:
                month_offset += 12
                year_offset -= 1

            date_from = datetime(year_offset, month_offset, 1)
            date_to = datetime(year_offset + 1, 1, 1) if month_offset == 12 \
                      else datetime(year_offset, month_offset + 1, 1)

            month_name = month_names_uz[month_offset]

            sale_qty = self._get_sale_order_qty(product_id, date_from, date_to)
            transfer_qty = self._get_intercompany_transfer_qty(product_id, date_from, date_to)
            monthly_sales[month_name] = round(sale_qty + transfer_qty, 2)

        return monthly_sales

    def get_batch_inventory_data(self, product_names, days=30):
        """
        Barcha tovarlar uchun zaxira va sotuvlarni bitta (batch) so'rovda oladi.
        Tezlikni 5-10 barobarga oshiradi.
        """
        results = {}
        pid_to_name = {}
        
        # 1. Barcha tovarlarning ID larini topib olamiz
        for name in product_names:
            p = self._find_product(name)
            if p:
                pid = p['id']
                pid_to_name[pid] = name
                results[name] = {
                    'name': name,
                    'stock_qty': 0.0,
                    'sales_qty': 0.0,
                    'sales_b2b': 0.0,
                    'transfer_urikzor': 0.0,
                    'transfer_qoqon': 0.0,
                    'history': {}
                }
                
        pids = list(pid_to_name.keys())
        if not pids:
            return results
            
        # 2. Barcha zaxiralarni bitta so'rov bilan olamiz
        quant_domain = [
            ('product_id', 'in', pids),
            ('location_id.usage', '=', 'internal'),
            ('location_id.company_id', '=', B2B_COMPANY_ID)
        ]
        quants = self._exec('stock.quant', 'search_read', quant_domain, ['product_id', 'quantity'])
        for q in quants:
            pid = q['product_id'][0]
            if pid in pid_to_name:
                results[pid_to_name[pid]]['stock_qty'] += q.get('quantity', 0.0)
                
        # 3. Barcha sotuvlarni bitta so'rov bilan olamiz
        date_from = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d 00:00:00')
        sale_domain = [
            ('product_id', 'in', pids),
            ('state', 'in', ['sale', 'done']),
            ('order_id.company_id', '=', B2B_COMPANY_ID),
            ('order_id.date_order', '>=', date_from)
        ]
        sale_lines = self._exec('sale.order.line', 'search_read', sale_domain, ['product_id', 'product_uom_qty'])
        for s in sale_lines:
            pid = s['product_id'][0]
            if pid in pid_to_name:
                qty = s.get('product_uom_qty', 0.0)
                results[pid_to_name[pid]]['sales_qty'] += qty
                results[pid_to_name[pid]]['sales_b2b'] += qty
                
        # 4. Barcha transferlarni bitta so'rov bilan olamiz
        ic_domain = [
            ('company_from_id', '=', 3),
            ('state', '=', 'done'),
            ('scheduled_date', '>=', date_from)
        ]
        transfers = self._exec('intercompany.transfer', 'search_read', ic_domain, ['id', 'company_to_id'])
        if transfers:
            tids = [t['id'] for t in transfers]
            
            transfer_dest = {}
            for t in transfers:
                if t.get('company_to_id'):
                    transfer_dest[t['id']] = t['company_to_id'][0]
                    
            line_domain = [
                ('transfer_id', 'in', tids),
                ('product_id', 'in', pids)
            ]
            ic_lines = self._exec('intercompany.transfer.line', 'search_read', line_domain, ['product_id', 'quantity', 'transfer_id'])
            for il in ic_lines:
                pid = il['product_id'][0]
                if pid in pid_to_name:
                    qty = il.get('quantity', 0.0)
                    results[pid_to_name[pid]]['sales_qty'] += qty
                    
                    tid = il['transfer_id'][0]
                    dest_id = transfer_dest.get(tid)
                    if dest_id == 2:
                        results[pid_to_name[pid]]['transfer_urikzor'] += qty
                    elif dest_id == 4:
                        results[pid_to_name[pid]]['transfer_qoqon'] += qty
                        
        # 5. Tarixiy 6 oylik ma'lumotlarni olish (Pivot jadval uchun)
        month_names_uz = {
            1: 'Yanvar', 2: 'Fevral', 3: 'Mart', 4: 'Aprel',
            5: 'May', 6: 'Iyun', 7: 'Iyul', 8: 'Avgust',
            9: 'Sentabr', 10: 'Oktabr', 11: 'Noyabr', 12: 'Dekabr'
        }
        now = datetime.now()
        for i in range(5, -1, -1):
            mo = now.month - i
            yr = now.year
            while mo <= 0:
                mo += 12
                yr -= 1
            
            d_from = datetime(yr, mo, 1)
            d_to = datetime(yr + 1, 1, 1) if mo == 12 else datetime(yr, mo + 1, 1)
            month_label = f"{month_names_uz[mo]} {yr}"
            
            # Har bir tovarning history dict-iga nolinchi qiymat kiritish
            for pid in pids:
                results[pid_to_name[pid]]['history'][month_label] = 0.0
                
            s_domain = [
                ('product_id', 'in', pids),
                ('state', 'in', ['sale', 'done']),
                ('order_id.company_id', '=', B2B_COMPANY_ID),
                ('order_id.date_order', '>=', d_from.strftime('%Y-%m-%d 00:00:00')),
                ('order_id.date_order', '<', d_to.strftime('%Y-%m-%d 00:00:00'))
            ]
            s_lines = self._exec('sale.order.line', 'search_read', s_domain, ['product_id', 'product_uom_qty'])
            for sl in s_lines:
                pid = sl['product_id'][0]
                if pid in pid_to_name:
                    results[pid_to_name[pid]]['history'][month_label] += sl.get('product_uom_qty', 0.0)
                    
            ic_dom = [
                ('company_from_id', '=', 3),
                ('state', '=', 'done'),
                ('scheduled_date', '>=', d_from.strftime('%Y-%m-%d 00:00:00')),
                ('scheduled_date', '<', d_to.strftime('%Y-%m-%d 00:00:00'))
            ]
            tr = self._exec('intercompany.transfer', 'search_read', ic_dom, ['id'])
            if tr:
                tr_ids = [t['id'] for t in tr]
                tr_lines = self._exec('intercompany.transfer.line', 'search_read', [
                    ('transfer_id', 'in', tr_ids),
                    ('product_id', 'in', pids)
                ], ['product_id', 'quantity'])
                for tl in tr_lines:
                    pid = tl['product_id'][0]
                    if pid in pid_to_name:
                        results[pid_to_name[pid]]['history'][month_label] += tl.get('quantity', 0.0)
                        
        return results

    def get_sales_total_30d(self, product_id):
        """Oxirgi 1 oydagi (30 kun) jami sotuv: B2B prodaja + intercompany transfer"""
        date_from = datetime.now() - timedelta(days=30)
        sale_qty = self._get_sale_order_qty(product_id, date_from)
        transfer_qty = self._get_intercompany_transfer_qty(product_id, date_from)
        return round(sale_qty + transfer_qty, 2)

    def get_sales_statistics(self, product_id, num_months=5):
        """
        Oxirgi 5 oydagi B2B statistikasi:
        - Menenjerlar bo'yicha sotuv (faqat B2B, faqat aktiv zakazlar)
        - Intercompany transferlar alohida ko'rsatiladi
        - Eng arzon va eng qimmat sotuv narxi
        """
        date_from = datetime.now() - timedelta(days=30 * num_months)
        date_from_str = date_from.strftime('%Y-%m-%d %H:%M:%S')
        
        # B2B sale order lines (faqat aktiv)
        domain = [
            ('product_id', '=', product_id),
            ('state', 'in', ['sale', 'done']),
            ('order_id.company_id', '=', B2B_COMPANY_ID),
            ('order_id.date_order', '>=', date_from_str),
        ]
        order_lines = self._exec('sale.order.line', 'search_read',
            domain, ['product_uom_qty', 'price_unit', 'salesman_id', 'order_id']
        )
        
        manager_sales = {}
        min_price = None
        min_order = None
        max_price = None
        max_order = None
        
        for line in order_lines:
            qty = line.get('product_uom_qty', 0)
            if qty <= 0:
                continue
            
            price = line.get('price_unit', 0)
            order_name = line.get('order_id', [0, "Noma'lum"])[1]
            manager = line.get('salesman_id')
            manager_name = manager[1] if manager else "Noma'lum menenjer"
            
            manager_sales[manager_name] = manager_sales.get(manager_name, 0) + qty
            
            if price > 0:
                if min_price is None or price < min_price:
                    min_price = price
                    min_order = order_name
                if max_price is None or price > max_price:
                    max_price = price
                    max_order = order_name
        
        # Intercompany transferlar ham sotuv sifatida qo'shiladi
        transfer_qty = self._get_intercompany_transfer_qty(product_id, date_from)
        if transfer_qty > 0:
            manager_sales["🔄 Intercompany Transfer"] = \
                manager_sales.get("🔄 Intercompany Transfer", 0) + transfer_qty
                
        return {
            'manager_sales': manager_sales,
            'min_price': min_price,
            'min_order': min_order,
            'max_price': max_price,
            'max_order': max_order
        }

    def get_last_purchase(self, product_id):
        """B2B kompaniyasiga tegishli oxirgi kirim (prixod)"""
        domain = [
            ('product_id', '=', product_id),
            ('state', 'in', ['purchase', 'done']),
            ('order_id.company_id', '=', B2B_COMPANY_ID),
        ]
        order_lines = self._exec('purchase.order.line', 'search_read',
            domain, ['product_qty', 'price_unit', 'order_id', 'partner_id'],
            order='id desc', limit=1
        )
        
        if not order_lines:
            return None
            
        line = order_lines[0]
        order_id = line['order_id'][0] if line.get('order_id') else None
        date_order = "Noma'lum sana"
        
        if order_id:
            order = self.models.execute_kw(self.db, self.uid, self.password,
                'purchase.order', 'read',
                [[order_id]], {'fields': ['date_order']}
            )
            if order:
                raw_date = order[0].get('date_order', '')
                date_order = raw_date[:10] if raw_date else "Noma'lum sana"
        
        partner = line.get('partner_id')
        return {
            'qty': line.get('product_qty', 0),
            'price': line.get('price_unit', 0),
            'partner': partner[1] if partner else "Noma'lum",
            'date': date_order
        }

    def get_general_stats(self):
        """Odoo dan umumiy qiziqarli statistikalarni oladi"""
        stats = []
        
        # 1. Xodimlar soni
        try:
            emp_count = self.models.execute_kw(self.db, self.uid, self.password, 'hr.employee', 'search_count', [[]])
            stats.append(f"Jami xodimlar soni: {emp_count} ta")
        except Exception:
            pass

        # 2. Bugungi sotuvlar
        from datetime import datetime
        today_str = datetime.utcnow().strftime('%Y-%m-%d 00:00:00')
        try:
            sales = self._exec('sale.order', 'search_read', [('date_order', '>=', today_str), ('state', 'in', ['sale', 'done'])], ['amount_total', 'company_id'])
            total_sum = sum(s.get('amount_total', 0) for s in sales)
            stats.append(f"Bugungi jami sotuvlar summasi: {total_sum} sum")
        except Exception:
            pass
            
        if not stats:
            return "Hech qanday statistika topilmadi yoki ruxsat yo'q."
            
        return "\n".join(stats)

    def create_sale_order(self, client_name: str, product_name: str, qty: float, price: float, pricelist_name: str = None) -> str:
        """
        Odoo'da avtomatik ravishda Sale Order (Sotuv) yaratadi.
        """
        try:
            qty_f = float(qty)
            price_f = float(price)
        except ValueError:
            return "Xato: Miqdor va narx raqam bo'lishi kerak."
            
        try:
            partner = self.models.execute_kw(self.db, self.uid, self.password,
                'res.partner', 'search_read',
                [[('name', 'ilike', client_name)]],
                {'limit': 1, 'fields': ['id', 'name', 'x_studio_category', 'total_overdue']})
            if not partner:
                return f"Xato: '{client_name}' ismli mijoz topilmadi."
            p = partner[0]
            
            category = p.get('x_studio_category', 'Noma\'lum')
            overdue = p.get('total_overdue', 0)
            if category in ['B', 'C'] and overdue > 10:
                return f"DIQQAT: {p['name']} ({category} toifa) da {overdue:,.2f} $ muddati o'tgan qarz bor! Prodaja urish taqiqlandi."
                
            product = self.models.execute_kw(self.db, self.uid, self.password,
                'product.product', 'search_read',
                [[('name', 'ilike', product_name)]],
                {'limit': 1, 'fields': ['id', 'name', 'virtual_available']})
            if not product:
                return f"Xato: '{product_name}' nomli tovar topilmadi."
            pr = product[0]
            
            if pr.get('virtual_available', 0) < qty_f:
                return f"Xato: Omborda yetarli erkin qoldiq yo'q. Erkin qoldiq: {pr.get('virtual_available', 0)}"
                
            sale_vals = {'partner_id': p['id']}
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
                
            return f"✅ Muvaffaqiyatli! {p['name']} ga {qty_f} ta {pr['name']} sotildi va tasdiqlandi. (Nakladnoy raqami: {sale_name})"
        except Exception as e:
            return f"Odoo xatosi: {e}"

    def create_reservation(self, client_name: str, product_name: str, qty: float, pricelist_name: str = None) -> str:
        """
        Mijoz uchun tovarni bron qiladi (Draft Sale Order orqali zaxira qilib bo'lmaydi, biz uni tasdiqlangan va yetkazib berishsiz holatda saqlaymiz yoki mijoz qarzlarini e'tiborga olmaymiz)
        Bron qilish bu xuddi prodajaga o'xshaydi, lekin qarz cheklovsiz.
        """
        try:
            qty_f = float(qty)
        except ValueError:
            return "Xato: Miqdor raqam bo'lishi kerak."
            
        try:
            partner = self.models.execute_kw(self.db, self.uid, self.password,
                'res.partner', 'search_read',
                [[('name', 'ilike', client_name)]],
                {'limit': 1, 'fields': ['id', 'name']})
            if not partner:
                return f"Xato: '{client_name}' ismli mijoz topilmadi."
            p = partner[0]
            
            product = self.models.execute_kw(self.db, self.uid, self.password,
                'product.product', 'search_read',
                [[('name', 'ilike', product_name)]],
                {'limit': 1, 'fields': ['id', 'name', 'virtual_available', 'lst_price']})
            if not product:
                return f"Xato: '{product_name}' nomli tovar topilmadi."
            pr = product[0]
            
            if pr.get('virtual_available', 0) < qty_f:
                return f"Xato: Omborda yetarli erkin qoldiq yo'q. Erkin qoldiq: {pr.get('virtual_available', 0)}"
                
            sale_vals = {'partner_id': p['id']}
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
                
            return f"🛡 Muvaffaqiyatli! {qty_f} ta {pr['name']} tovari {p['name']} uchun bron qilindi (Sotuv raqami: {sale_name})."
        except Exception as e:
            return f"Odoo xatosi: {e}"

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
                
            # Check related pickings
            picking_ids = orders[0].get('picking_ids', [])
            if picking_ids:
                pickings = self.models.execute_kw(self.db, self.uid, self.password,
                    'stock.picking', 'read', [picking_ids], {'fields': ['id', 'state', 'name']})
                for pick in pickings:
                    if pick['state'] == 'done':
                        return f"❌ {order_name} ni bekor qilib bo'lmaydi! Unga ulangan dostavka ({pick['name']}) allaqachon bajarilgan (done)."
                
                # Cancel pickings
                for pick in pickings:
                    if pick['state'] not in ('cancel', 'done'):
                        self.models.execute_kw(self.db, self.uid, self.password, 'stock.picking', 'action_cancel', [[pick['id']]])
            
            # Finally cancel sale order
            self.models.execute_kw(self.db, self.uid, self.password,
                'sale.order', 'action_cancel', [[order_id]])
            return f"✅ {order_name} nakladnoy muvaffaqiyatli bekor qilindi."
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
            return "\n".join(res)
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

    def get_accounting_reports(self, report_type: str, company_id: int = 1, account_code: str = None, partner_name: str = None) -> str:
        try:
            from datetime import datetime
            today_str = datetime.now().strftime('%Y-%m-%d')
            
            if report_type == 'partner_debts':
                domain = [('supplier_rank', '>', 0)]
                if partner_name:
                    domain.append(('name', 'ilike', partner_name))
                partners = self.models.execute_kw(self.db, self.uid, self.password, 'res.partner', 'search_read', [domain], {'fields': ['id', 'name', 'credit', 'debit']})
                if not partners:
                    return "Bunday yetkazib beruvchi topilmadi."
                
                res = "📊 YETKAZIB BERUVCHILAR QARZI:\n"
                for p in partners[:15]:
                    if p['credit'] > 0 or p['debit'] > 0:
                        overdue = 0.0
                        if p['credit'] > 0:
                            inv_domain = [('partner_id', '=', p['id']), ('move_type', 'in', ['in_invoice', 'in_receipt']), ('payment_state', 'in', ['not_paid', 'partial']), ('invoice_date_due', '<', today_str)]
                            overdue_invs = self.models.execute_kw(self.db, self.uid, self.password, 'account.move', 'search_read', [inv_domain], {'fields': ['amount_residual']})
                            overdue = sum(inv['amount_residual'] for inv in overdue_invs)
                        
                        res += f"\n👤 {p['name']}\n"
                        if p['credit'] > 0:
                            res += f"   ➖ Bizning qarzimiz: {p['credit']:,.2f}\n"
                            res += f"   ⚠️ Shundan prosrochka: {overdue:,.2f}\n"
                            res += f"   ⏳ Hali muddati bor: {p['credit'] - overdue:,.2f}\n"
                        if p['debit'] > 0:
                            res += f"   ➕ Ularning qarzi: {p['debit']:,.2f}\n"
                return res

            elif report_type == 'account_balance':
                if not account_code: return "account_code (masalan '1412') kerak."
                domain = [('account_id.code', '=', account_code)]
                if company_id:
                    domain.append(('company_id', '=', company_id))
                
                lines = self.models.execute_kw(self.db, self.uid, self.password, 'account.move.line', 'search_read', [domain], {'fields': ['balance', 'amount_currency', 'currency_id']})
                if not lines: return f"🏦 Shot {account_code} bo'yicha qoldiq yo'q."
                
                total_balance = sum(l.get('balance', 0) for l in lines)
                total_currency = sum(l.get('amount_currency', 0) for l in lines)
                
                res = f"🏦 Shot {account_code} qoldig'i (Kompaniya ID: {company_id}):\n"
                res += f"💵 So'mda (Bazaviy): {total_balance:,.2f}\n"
                if total_currency != 0:
                    res += f"💲 Valyutada: {total_currency:,.2f}\n"
                return res

            elif report_type == 'daily_cash':
                domain = [('date', '=', today_str)]
                if company_id:
                    domain.append(('company_id', '=', company_id))
                payments = self.models.execute_kw(self.db, self.uid, self.password, 'account.payment', 'search_read', [domain], {'fields': ['payment_type', 'amount', 'partner_id', 'journal_id', 'state']})
                if not payments: return f"📅 Bugun ({today_str}) uchun kassa aylanmasi topilmadi."
                
                inflows = sum(p['amount'] for p in payments if p['payment_type'] == 'inbound' and p['state'] == 'posted')
                outflows = sum(p['amount'] for p in payments if p['payment_type'] == 'outbound' and p['state'] == 'posted')
                
                res = f"📅 Kunlik aylanma ({today_str}):\n"
                res += f"📥 Kirim: {inflows:,.2f}\n"
                res += f"📤 Chiqim (To'lovlar): {outflows:,.2f}\n"
                return res

            return "❌ Noma'lum report_type"
        except Exception as e:
            return f"Accounting xatosi: {e}"

    def get_inventory_analytics(self, product_name: str) -> str:
        try:
            products = self.models.execute_kw(self.db, self.uid, self.password, 'product.product', 'search_read', 
                [[('name', 'ilike', product_name)]], {'fields': ['id', 'name', 'qty_available', 'incoming_qty', 'outgoing_qty', 'free_qty'], 'limit': 3})
            
            if not products:
                return f"Omborda '{product_name}' nomli tovar topilmadi."
            
            res = f"📦 SKLAD ANALITIKASI ('{product_name}'):\n"
            for p in products:
                res += f"\n🔸 {p['name']}\n"
                res += f"   - Erkin qoldiq (Sotishga tayyor): {p.get('free_qty', 0):,.2f}\n"
                res += f"   - Band qilingan (Zabronirovanno): {p.get('outgoing_qty', 0):,.2f}\n"
                res += f"   - Yo'ldagi (Kutilyotgan): {p.get('incoming_qty', 0):,.2f}\n"
                res += f"   - Jami qoldiq (Fizicheskiy): {p.get('qty_available', 0):,.2f}\n"
            return res
        except Exception as e:
            return f"Inventory xatosi: {e}"

    def get_client_profile(self, partner_name: str) -> str:
        try:
            partners = self.models.execute_kw(self.db, self.uid, self.password, 'res.partner', 'search_read', 
                [[('name', 'ilike', partner_name)]], {'fields': ['id', 'name', 'credit', 'debit', 'total_invoiced', 'create_date'], 'limit': 1})
            
            if not partners:
                return f"'{partner_name}' nomli mijoz/hamkor topilmadi."
                
            p = partners[0]
            partner_id = p['id']
            
            # Oxirgi xaridni topish
            last_order = self.models.execute_kw(self.db, self.uid, self.password, 'sale.order', 'search_read', 
                [[('partner_id', '=', partner_id), ('state', 'in', ['sale', 'done'])]], {'fields': ['date_order', 'amount_total'], 'order': 'date_order desc', 'limit': 1})
            
            res = f"👤 MIJOZ 360 PROFILI: {p['name']}\n"
            res += f"-----------------------------------------\n"
            res += f"💰 Umumiy savdo aylanmasi (Tarix): {p.get('total_invoiced', 0):,.2f}\n"
            res += f"➖ Bizning qarzimiz: {p.get('credit', 0):,.2f}\n"
            res += f"➕ Ularning qarzi (Debitor): {p.get('debit', 0):,.2f}\n"
            
            if last_order:
                lo = last_order[0]
                res += f"🛒 Oxirgi xarid: {lo['date_order']} (Summa: {lo['amount_total']:,.2f})\n"
            else:
                res += f"🛒 Oxirgi xarid: Hech narsa sotib olmagan.\n"
            
            return res
        except Exception as e:
            return f"Client Profile xatosi: {e}"

    def create_intercompany_transfer_bulk(self, source_warehouse_id: int, dest_company_id: int, dest_warehouse_id: int, items: list) -> str:
        """
        B2B dan boshqa kompaniyaga bitta hujjat ichida bir nechta tovar (line) yaratish.
        items = [{'product_name': '...', 'qty': 100}, ...]
        """
        try:
            picking_type_from_id = False
            location_from_id = False
            if source_warehouse_id == 4:
                picking_type_from_id = 47
                location_from_id = 47
            elif source_warehouse_id == 7:
                picking_type_from_id = 90
                location_from_id = 79
                
            picking_type_to_id = False
            location_to_id = False
            if dest_warehouse_id == 3:
                picking_type_to_id = 34
                location_to_id = 34
                
            # Transfer hujjatini boshida yaratib olamiz
            vals = {
                'company_from_id': 3, # B2B_COMPANY_ID
                'warehouse_from_id': source_warehouse_id,
                'company_to_id': dest_company_id,
                'warehouse_to_id': dest_warehouse_id,
                'picking_type_from_id': picking_type_from_id,
                'location_from_id': location_from_id,
                'picking_type_to_id': picking_type_to_id,
                'location_to_id': location_to_id,
                'transit_location_id': 98,
                'state': 'draft'
            }
            transfer_id = self.models.execute_kw(self.db, self.uid, self.password,
                'intercompany.transfer', 'create', [vals])
                
            added_lines = 0
            errors = []
            
            # Har bir tovar uchun Line qo'shamiz
            for item in items:
                p_name = item.get('product_name')
                qty_f = float(item.get('qty', 0))
                
                product = self._find_product(p_name)
                if not product:
                    errors.append(f"'{p_name}' topilmadi")
                    continue
                    
                line_vals = {
                    'transfer_id': transfer_id,
                    'product_id': product['id'],
                    'quantity': qty_f,
                    'uom_id': product['uom_id'][0] if product.get('uom_id') else 1
                }
                
                self.models.execute_kw(self.db, self.uid, self.password,
                    'intercompany.transfer.line', 'create', [line_vals])
                added_lines += 1
                
            if added_lines == 0:
                # Agar bitta ham tovar tushmasa o'chirib tashlaymiz
                self.models.execute_kw(self.db, self.uid, self.password,
                    'intercompany.transfer', 'unlink', [[transfer_id]])
                return f"Xato: Barcha tovarlar xato kiritilgan. {errors}"
            
            # Tasdiqlash
            self.models.execute_kw(self.db, self.uid, self.password,
                'intercompany.transfer', 'action_confirm', [[transfer_id]])
            
            return f"✅ Intercompany Transfer yaratildi va Tasdiqlandi (Confirmed)! Hujjat ID: {transfer_id} ({added_lines} ta qator)"
        except Exception as e:
            return f"Intercompany Xatosi: {e}"
