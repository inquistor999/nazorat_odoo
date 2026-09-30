import asyncio
from odoo_client import OdooClient

def test_reservation():
    client = OdooClient()
    
    client_name = "Abdullaev Xasan"
    product1 = "Sorbat kaliya (FOODS)"
    product2 = "Lesitin" # wait, we'll use Jele PREMIUM SHOKOLAD KEKSAN (7kg) (JAMI)
    
    print("Creating reservation 1...")
    res1 = client.create_reservation(client_name, product1, 10.0)
    print("Res 1:", res1)
    
    print("Creating reservation 2...")
    res2 = client.create_reservation(client_name, "Jele PREMIUM SHOKOLAD KEKSAN (7kg) (JAMI)", 5.0)
    print("Res 2:", res2)

if __name__ == "__main__":
    test_reservation()
