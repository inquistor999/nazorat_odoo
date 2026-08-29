import matplotlib.pyplot as plt
import io

import re

def extract_package_info(product_name):
    """Mahsulot nomidan qadoq og'irligini va o'lchov birligini ajratib oladi"""
    # kg uchun qidiruv
    match_kg = re.search(r'\((\d+(?:\.\d+)?)\s*kg\)', product_name, re.IGNORECASE)
    if match_kg:
        return {'weight_kg': float(match_kg.group(1)), 'is_gram': False}
        
    # gr uchun qidiruv
    match_gr = re.search(r'\((\d+(?:\.\d+)?)\s*gr\)', product_name, re.IGNORECASE)
    if match_gr:
        return {'weight_kg': float(match_gr.group(1)) / 1000.0, 'is_gram': True}
        
    return {'weight_kg': 1.0, 'is_gram': False}

def calculate_reorder_qty(product_name, current_stock, sales_last_90_days, lead_time_days=3, target_days=30):
    """
    Zakaz miqdorini hisoblaydigan funksiya.
    lead_time_days: Zakaz yetib kelishiga ketadigan vaqt (masalan, 3 kun)
    target_days: Bizga qancha vaqtga yetadigan zaxira kerak? (masalan, 1 oy = 30 kun)
    """
    # Oxirgi 3 oydagi o'rtacha kunlik sotuv
    daily_sales = sales_last_90_days / 90 if sales_last_90_days > 0 else 0
    
    # Kelgusi (30 kun + yetkazish vaqti) uchun jami qancha tovar kerak?
    needed_for_period = daily_sales * (target_days + lead_time_days)
    
    # Qancha zakaz qilish kerak (kerakli miqdordan hozirgi zaxirani ayiramiz)
    reorder_qty = needed_for_period - current_stock
    
    # Qadoq og'irligini aniqlash va shunga karrali qilib yaxlitlash
    pkg_info = extract_package_info(product_name)
    pkg_weight_kg = pkg_info['weight_kg']
    
    if reorder_qty > 0:
        pieces = int(round(reorder_qty / pkg_weight_kg))
        reorder_qty_kg = round(pieces * pkg_weight_kg, 2)
    else:
        reorder_qty_kg = 0
        pieces = 0
    
    return {
        'daily_sales': round(daily_sales, 2),
        'needed_for_period': round(needed_for_period, 2),
        'reorder_qty': reorder_qty_kg,
        'pieces': pieces,
        'is_gram': pkg_info['is_gram']
    }

def create_sales_history_chart(product_name, monthly_sales):
    """Oxirgi oylardagi sotuvlarni ifodalovchi ustunli diagramma yaratish"""
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor('#1e1e2e')
    ax.set_facecolor('#1e1e2e')
    
    months = list(monthly_sales.keys())
    values = list(monthly_sales.values())
    
    bars = ax.bar(months, values, color='#3b82f6', width=0.5, edgecolor='#60a5fa', linewidth=1.5, zorder=3)
    
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:g}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', color='#f8fafc', fontweight='bold', fontsize=10)
    
    ax.set_title(f"📊 {product_name}\nSotuvlar tarixi", color='#f8fafc', pad=20, fontsize=14, fontweight='bold')
    ax.set_ylabel("Sotilgan miqdor (kg/ta)", color='#94a3b8', fontsize=11)
    
    ax.grid(True, axis='y', color='#334155', linestyle='--', alpha=0.7, zorder=0)
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#334155')
    ax.spines['bottom'].set_color('#334155')
    
    ax.tick_params(axis='x', colors='#cbd5e1', labelsize=11)
    ax.tick_params(axis='y', colors='#94a3b8', labelsize=10)
    
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    
    return buf
