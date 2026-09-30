import asyncio

from ai_agent import ai_assistant
from odoo_client import OdooClient

async def test():
    client = OdooClient()
    print("Caching products...")
    prods = client.get_all_product_names_cached()
    print(f"Loaded {len(prods)} products from cache.")
    
    order = "Zakaz: jele torto shokoald 15kg"
    
    print("Testing parser...")
    parsed = await ai_assistant.parse_order_with_gemini(order, prods)
    print("Parsed JSON:", parsed)

if __name__ == "__main__":
    asyncio.run(test())
