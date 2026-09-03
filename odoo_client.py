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

    def get_sales_total_6m(self, product_id):
        """Oxirgi 6 oydagi (180 kun) jami sotuv: B2B prodaja + intercompany transfer"""
        date_from = datetime.now() - timedelta(days=180)
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
