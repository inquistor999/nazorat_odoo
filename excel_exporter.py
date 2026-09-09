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

def generate_monthly_sales_excel(company_id, months, company_name, selected_months=None, product_id=None):
    odoo = OdooClient()
    
    # 1. Sana oralig'ini aniqlash
    now = datetime.now()
    if selected_months:
        # selected_months: ['2023-08', '2023-07']
        min_y, min_m = 9999, 12
        for m_str in selected_months:
            y, m = map(int, m_str.split('-'))
            if y < min_y or (y == min_y and m < min_m):
                min_y, min_m = y, m
        date_from_dt = datetime(min_y, min_m, 1)
    else:
        month_offset = now.month - months + 1
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
    if product_id:
        domain.append(('product_id', '=', product_id))
    
    logging.info(f"Odoo dan {company_name} uchun {months} oylik ma'lumotlar tortilmoqda...")
    
    # Katta datani bittada olish
    order_lines = odoo._exec('sale.order.line', 'search_read', 
                             domain, 
                             ['product_id', 'product_uom_qty', 'price_unit', 'order_id', 'currency_id'])
    
    if not order_lines:
        return None
        
    # UZS kursini Odoo dan olib kelamiz
    currencies = odoo._exec('res.currency', 'search_read', [('name', '=', 'UZS')], ['rate'])
    uzs_rate = currencies[0]['rate'] if currencies and currencies[0].get('rate') else 12500.0
        
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
        
        # Agar narx So'mda (UZS) bo'lsa, Dollarga ($) aylantiramiz
        currency = line.get('currency_id')
        if currency and isinstance(currency, list) and len(currency) > 1 and currency[1] == 'UZS':
            price_unit = price_unit / uzs_rate
        
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
        
        if selected_months:
            m_str = f"{dt.year}-{dt.month:02d}"
            if m_str not in selected_months:
                continue
        
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
    
    # Barcha kutilayotgan oylarni aniqlash
    expected_months = []
    month_names_uz = {
        1: 'Yanvar', 2: 'Fevral', 3: 'Mart', 4: 'Aprel',
        5: 'May', 6: 'Iyun', 7: 'Iyul', 8: 'Avgust',
        9: 'Sentabr', 10: 'Oktabr', 11: 'Noyabr', 12: 'Dekabr'
    }
    
    if selected_months:
        sorted_m = sorted(selected_months)
        for m_str in sorted_m:
            y, m = map(int, m_str.split('-'))
            expected_months.append(f"{month_names_uz[m]} {y}")
    else:
        y, m = date_from_dt.year, date_from_dt.month
        end_y, end_m = datetime.now().year, datetime.now().month
        while True:
            expected_months.append(f"{month_names_uz[m]} {y}")
            if y > end_y or (y == end_y and m >= end_m):
                break
            m += 1
            if m > 12:
                m = 1
                y += 1
                
    # Pivot jadval yaratish
    pivot_df = pd.pivot_table(
        df, 
        values='Sotuv Kg', 
        index='Tovar nomi', 
        columns='Oy', 
        aggfunc='sum', 
        fill_value=0
    ).reset_index()
    
    # Yetishmayotgan oylarni 0 bilan to'ldirish
    for m_name in expected_months:
        if m_name not in pivot_df.columns:
            pivot_df[m_name] = 0
            
    # Ustunlarni xronologik tartibga solish
    cols = ['Tovar nomi'] + expected_months
    pivot_df = pivot_df[cols]
    
    # Jami hisoblash
    pivot_df['Итого (Jami)'] = pivot_df[expected_months].sum(axis=1)
    
    # Tovar nomlari bo'yicha A-Z saralash
    pivot_df = pivot_df.sort_values(by='Tovar nomi')
    
    # Formatlash
    for col in pivot_df.columns:
        if col != 'Tovar nomi':
            pivot_df[col] = pivot_df[col].round(2)
            
    # Excel fayl yaratish
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pivot_df.to_excel(writer, sheet_name='Oylik Statistika', index=False)
        
        # Premium dizayn (ustunlarni moslashtirish)
        worksheet = writer.sheets['Oylik Statistika']
        for idx, col in enumerate(pivot_df.columns):
            max_len = max(
                pivot_df[col].astype(str).map(len).max(),
                len(col)
            ) + 2
            col_letter = chr(65 + idx)
            worksheet.column_dimensions[col_letter].width = max_len
            
    output.seek(0)
    return output

def generate_reorder_excel(items):
    """
    Zakaz qilinishi kerak bo'lgan tovarlar ro'yxatini Excelga yozadi.
    items: dict lardan iborat ro'yxat
    """
    if not items:
        return None
        
    records = []
    month_columns = []
    if items and 'history' in items[0]:
        month_columns = list(items[0]['history'].keys())
        # Reverse them if needed so oldest is first. 
        # In odoo_client, we appended from oldest (5 months ago) to newest (now)
        # So they are already in the correct order: oldest to newest.

    for item in items:
        row = {
            'Tovar nomi': item.get('name', ''),
            'Hozirgi qoldiq (kg)': item.get('stock_qty', 0),
            'Zakaz miqdori (kg)': item.get('reorder_qty', 0),
            'Qadoqlar soni': item.get('pieces', 0)
        }
        
        # Oylik sotuvlarni qo'shish
        total_hist = 0.0
        for m in month_columns:
            qty = item.get('history', {}).get(m, 0.0)
            row[m] = round(qty, 2)
            total_hist += qty
            
        row['Итого (Jami 6 oylik)'] = round(total_hist, 2)
        
        # Qolgan esktra infolar oxiriga qo'shib qo'yamiz
        row['1 Oylik Jami sotuv (kg)'] = item.get('sales_qty', 0)
        row['Qoldiq yetadigan kun'] = item.get('days_left', 0)
        
        records.append(row)
        
    # Alifbo tartibida saralash (Premium rasmda shunday edi)
    records.sort(key=lambda x: x['Tovar nomi'].lower())
        
    import pandas as pd
    import io
    df = pd.DataFrame(records)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Zakaz Qilish', index=False)
        
        worksheet = writer.sheets['Zakaz Qilish']
        for idx, col in enumerate(df.columns):
            max_len = max(
                df[col].astype(str).map(len).max(),
                len(col)
            ) + 2
            col_letter = chr(65 + idx)
            worksheet.column_dimensions[col_letter].width = max_len
            
    output.seek(0)
    return output
