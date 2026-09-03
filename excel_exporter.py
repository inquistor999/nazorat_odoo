import io
from datetime import datetime
import pandas as pd
from odoo_client import OdooClient
import logging

def extract_package_info(name):
    # Bu mavjud analiz helper funksiyasiga o'xshash
    # Shunchaki nomi va o'lchovini ajratib oladi
    import re
    match = re.search(r'\((\d+(?:\.\d+)?)\s*(kg|g)\)', name, re.IGNORECASE)
    if match:
        val = float(match.group(1))
        unit = match.group(2).lower()
        if unit == 'g':
            return {'weight_kg': val / 1000.0, 'is_gram': True}
        return {'weight_kg': val, 'is_gram': False}
    return {'weight_kg': 1.0, 'is_gram': False}

def generate_monthly_sales_excel(company_id, months, company_name):
    odoo = OdooClient()
    
    # 1. Sana oralig'ini aniqlash
    now = datetime.now()
    month_offset = now.month - months
    year_offset = now.year
    while month_offset <= 0:
        month_offset += 12
        year_offset -= 1
        
    date_from_dt = datetime(year_offset, month_offset, 1)
    date_from = date_from_dt.strftime('%Y-%m-%d 00:00:00')
    
    # 2. Shu filialdagi barcha prodajalarni tortib olish
    domain = [
        ('state', 'in', ['sale', 'done']),
        ('order_id.company_id', '=', company_id),
        ('order_id.date_order', '>=', date_from)
    ]
    
    logging.info(f"Odoo dan {company_name} uchun {months} oylik ma'lumotlar tortilmoqda...")
    
    # Katta datani bittada olish
    order_lines = odoo._exec('sale.order.line', 'search_read', 
                             domain, 
                             ['product_id', 'product_uom_qty', 'price_unit', 'order_id'])
    
    if not order_lines:
        return None
        
    # 3. Odoo'dan har bir buyurtma sanasini tortib olish (chunki sale.order.line da date_order yo'q)
    order_ids = list(set(line['order_id'][0] for line in order_lines if line.get('order_id')))
    orders = odoo._exec('sale.order', 'search_read',
                        [('id', 'in', order_ids)],
                        ['id', 'date_order'])
    order_date_map = {order['id']: order['date_order'] for order in orders}
    
    # 4. Ma'lumotlarni ishlash
    records = []
    for line in order_lines:
        if not line.get('product_id'): continue
        
        prod_id = line['product_id'][0]
        prod_name = line['product_id'][1]
        order_id = line['order_id'][0] if line.get('order_id') else None
        
        qty = line.get('product_uom_qty', 0)
        price_unit = line.get('price_unit', 0)
        
        # Kg hisobi
        pkg = extract_package_info(prod_name)
        kg = qty * pkg['weight_kg'] if pkg['is_gram'] else qty
        
        # Sana va oy
        date_str = order_date_map.get(order_id)
        if not date_str: continue
        
        # Odoo returns date in string format 'YYYY-MM-DD HH:MM:SS'
        # Sometimes it can be 'YYYY-MM-DD' depending on the field, but date_order is datetime.
        try:
            dt = datetime.strptime(str(date_str).split('.')[0], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            dt = datetime.strptime(str(date_str).split()[0], '%Y-%m-%d')
            
        month_names_uz = {
            1: 'Yanvar', 2: 'Fevral', 3: 'Mart', 4: 'Aprel',
            5: 'May', 6: 'Iyun', 7: 'Iyul', 8: 'Avgust',
            9: 'Sentabr', 10: 'Oktabr', 11: 'Noyabr', 12: 'Dekabr'
        }
        month_name = f"{month_names_uz[dt.month]} {dt.year}"
        
        records.append({
            'Tovar nomi': prod_name,
            'Oy': month_name,
            'Sotuv Kg': kg,
            '1 kg narxi ($)': price_unit,
            'Jami summa ($)': qty * price_unit,
            'month_idx': dt.year * 100 + dt.month
        })
        
    if not records:
        return None
        
    df = pd.DataFrame(records)
    
    # Grouplash
    # Har bir tovar va oy bo'yicha jami kg va summani hisoblash
    grouped = df.groupby(['Tovar nomi', 'Oy', 'month_idx']).agg({
        'Sotuv Kg': 'sum',
        'Jami summa ($)': 'sum',
        '1 kg narxi ($)': 'mean'  # O'rtacha narx
    }).reset_index()
    
    # Oylarni to'g'ri tartiblash
    grouped = grouped.sort_values(by=['Tovar nomi', 'month_idx'])
    grouped = grouped.drop(columns=['month_idx'])
    
    # Formatlash
    grouped['Sotuv Kg'] = grouped['Sotuv Kg'].round(2)
    grouped['Jami summa ($)'] = grouped['Jami summa ($)'].round(2)
    grouped['1 kg narxi ($)'] = grouped['1 kg narxi ($)'].round(2)
    
    # Excel fayl yaratish
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        grouped.to_excel(writer, sheet_name='Oylik Statistika', index=False)
        
        # Premium dizayn (ustunlarni moslashtirish)
        worksheet = writer.sheets['Oylik Statistika']
        for idx, col in enumerate(grouped.columns):
            max_len = max(
                grouped[col].astype(str).map(len).max(),
                len(col)
            ) + 2
            col_letter = chr(65 + idx)
            worksheet.column_dimensions[col_letter].width = max_len
            
    output.seek(0)
    return output
