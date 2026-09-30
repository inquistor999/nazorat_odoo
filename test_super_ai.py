import asyncio
from ai_agent import ai_assistant
import json

async def test_super_ai():
    with open('tracked_products.txt', 'r', encoding='utf-8') as f:
        products = [line.strip() for line in f.readlines() if line.strip()]
        
    order_text = """Zakaz:
    20 kg jele torto shokolad
    15 lesitin"""
    
    prompt = f"""Mijoz quyidagi zakazni yubordi:
"{order_text}"

Mana bizning Odoo bazamizdagi tovarlar ro'yxati:
{', '.join(products)}

Vazifangiz:
1. Zakaz matnidan har bir tovar nomini va miqdorini ajratib oling.
2. Mijoz yozgan tovar nomini ("lesitin", "jele torto") bizning bazadagi ro'yxatdan eng mos keluvchisiga almashtiring.
3. Agar umuman mos kelmaydigan bo'lsa, ro'yxatdan eng yaqinini tanlang.
4. Javobni FAQAT JSON formatida qaytaring, boshqa hech qanday izohsiz.

JSON formati:
[
  {{"raw_name": "mijoz yozgan xato nom", "matched_name": "bazadagi to'g'ri nom", "qty": 20.0}}
]
"""
    
    print("AI o'ylamoqda...")
    resp = await ai_assistant.generate_response(prompt, user_id=123)
    print("AI Javobi:")
    print(resp)

if __name__ == "__main__":
    asyncio.run(test_super_ai())
