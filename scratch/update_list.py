import os

file_path = "odoo_tools.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

old_list = """odoo_tools_list = [
    get_client_debt, 
    get_product_stock, 
    get_manager_clients_count, 
    create_sale_order, 
    create_reservation,
    universal_odoo_search,
    cancel_sale_order,
    get_reservation_details_tool,
    create_intercompany_transfer_tool
]"""

new_list = """odoo_tools_list = [
    get_client_debt, 
    get_product_stock, 
    get_manager_clients_count, 
    create_sale_order, 
    create_reservation,
    universal_odoo_search,
    cancel_sale_order,
    get_reservation_details_tool,
    create_intercompany_transfer_tool,
    save_learning_tool,
    check_product_availability_in_warehouse_tool,
    create_bron_tool,
    get_pending_bron_cancel_requests_tool,
    action_bron_cancel_request_tool
]"""

content = content.replace(old_list, new_list)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("odoo_tools_list updated!")
