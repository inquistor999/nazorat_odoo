import os
import re

odoo_tools_path = "odoo_tools.py"
ai_agent_path = "ai_agent.py"

with open(odoo_tools_path, "r", encoding="utf-8") as f:
    tools_content = f.read()

super_tools_code = """
def update_odoo_record(model_name: str, record_id: int, fields_to_update: dict) -> str:
    \"\"\"
    Odoo bazasidagi istalgan jadvaldagi (model) ma'lumotni qisman (chistichno) tahrirlaydi.
    Masalan, bron (sale.order.line) qilingan tovar miqdorini o'zgartirish (masalan 100 kg ga tushirish) uchun 'product_uom_qty' maydoni yangilanadi.
    Args:
        model_name: Odoo modeli (masalan 'sale.order.line').
        record_id: Tahrirlanadigan ma'lumotning ID raqami.
        fields_to_update: Yangilanadigan maydonlar lyg'ati (dictionary), masalan: {'product_uom_qty': 400.0}
    Returns:
        Amal natijasi haqida ma'lumot.
    \"\"\"
    try:
        from odoo_client import OdooClient
        client = OdooClient()
        success = client.models.execute_kw(client.db, client.uid, client.password,
            model_name, 'write', [[record_id], fields_to_update])
        if success:
            return f"✅ Muvaffaqiyatli! {model_name} (ID: {record_id}) dagi ma'lumotlar o'zgartirildi: {fields_to_update}"
        else:
            return f"❌ Xatolik yuz berdi. Tahrirlash amalga oshmadi."
    except Exception as e:
        return f"Xato: {e}"

def delete_odoo_record(model_name: str, record_ids: list) -> str:
    \"\"\"
    Odoo bazasidagi istalgan ma'lumotni TO'LIQ o'chirib yuboradi (unlink).
    Masalan, bekor qilingan nakladnoyning hali jo'natilmagan dostavkasini (stock.picking) butunlay o'chirish uchun.
    Args:
        model_name: Odoo modeli (masalan 'stock.picking' yoki 'sale.order').
        record_ids: O'chiriladigan ID lar ro'yxati (masalan [1234]).
    Returns:
        O'chirilganligi haqida xabar.
    \"\"\"
    try:
        from odoo_client import OdooClient
        client = OdooClient()
        success = client.models.execute_kw(client.db, client.uid, client.password,
            model_name, 'unlink', [record_ids])
        if success:
            return f"🚮 Muvaffaqiyatli o'chirildi! {model_name} jadvallari: {record_ids} to'liq olib tashlandi."
        else:
            return f"❌ O'chirishda xatolik yuz berdi. Ma'lumot boshqa hujjatlarga bog'langan bo'lishi mumkin."
    except Exception as e:
        return f"Xato: {e}"

def execute_odoo_button(model_name: str, method_name: str, record_ids: list) -> str:
    \"\"\"
    Odoo interfeysidagi istalgan tugmani (Method) bosish imkonini beradi.
    Masalan, Nakladnoyni bekor qilish uchun 'sale.order' da 'action_cancel' methodi ishlatiladi. Bronni tasdiqlash uchun 'action_confirm' ishlatiladi.
    Args:
        model_name: Odoo modeli (masalan 'sale.order').
        method_name: Bosiladigan tugmaning backend kodi (masalan 'action_cancel', 'action_confirm').
        record_ids: Qaysi hujjatlarda (ID) shu tugma bosilishi kerak (masalan [54321]).
    Returns:
        Tugma muvaffaqiyatli bosilganligi natijasi.
    \"\"\"
    try:
        from odoo_client import OdooClient
        client = OdooClient()
        client.models.execute_kw(client.db, client.uid, client.password,
            model_name, method_name, [record_ids])
        return f"🔘 '{method_name}' tugmasi {model_name} (ID: {record_ids}) uchun muvaffaqiyatli bosildi!"
    except Exception as e:
        return f"Tugma bosishda xatolik: {e}"

def execute_odoo_shell_command(python_code: str) -> str:
    \"\"\"
    Odoo serverida backend (shell) orqali to'g'ridan to'g'ri Python kod ishga tushirish imkonini beradi.
    Foydalanuvchi qatiy ravishda shell orqali bajarishni va o'z tasdig'ini (Ha) berganidan so'nggina ishlatiladi.
    Odoo environment `env` o'zgaruvchisi orqali taqdim etiladi.
    Args:
        python_code: Ishga tushiriladigan Odoo Python script kodi. Bu env.cr.execute() yoki env['model'].search() bo'lishi mumkin.
    Returns:
        Scriptning bajarilish natijasi yoki print qilingan ma'lumotlar.
    \"\"\"
    try:
        from odoo_client import OdooClient
        import xmlrpc.client
        client = OdooClient()
        
        # Odoo API orqali raw python ishga tushirib bo'lmaydi (xavfsizlik sababli).
        # Lekin biz buni qaysidir server action yoki base execute_kw vositasida 'ir.actions.server' orqali vaqtincha yaratib ishga tushirishimiz mumkin.
        # Bu juda ilg'or funksiya.
        
        action_vals = {
            'name': 'AI Shell Execution',
            'model_id': client.models.execute_kw(client.db, client.uid, client.password, 'ir.model', 'search', [[('model', '=', 'res.partner')]])[0],
            'state': 'code',
            'code': python_code
        }
        
        action_id = client.models.execute_kw(client.db, client.uid, client.password, 'ir.actions.server', 'create', [action_vals])
        
        result = client.models.execute_kw(client.db, client.uid, client.password, 'ir.actions.server', 'run', [[action_id]])
        
        # Tozalash
        client.models.execute_kw(client.db, client.uid, client.password, 'ir.actions.server', 'unlink', [[action_id]])
        
        return f"💻 Shell Script bajarildi. Natija: {result}"
    except Exception as e:
        return f"Shell Script Xatosi: {e}"
"""

# Append functions to odoo_tools.py
if "update_odoo_record" not in tools_content:
    with open(odoo_tools_path, "a", encoding="utf-8") as f:
        f.write("\n" + super_tools_code)

# Add to odoo_tools_list
old_list = "odoo_tools_list = [\n    universal_odoo_search,\n    get_odoo_fields,\n    get_product_free_qty,\n    check_product_availability_in_warehouse_tool,\n    create_nakladnoy_tool,\n    create_intercompany_transfer_tool,\n    cancel_nakladnoy_tool,\n    get_product_price,\n    create_bron_tool,\n    get_pending_bron_cancel_requests_tool,\n    action_bron_cancel_request_tool,\n    save_learning_tool\n]"

new_list = "odoo_tools_list = [\n    universal_odoo_search,\n    get_odoo_fields,\n    get_product_free_qty,\n    check_product_availability_in_warehouse_tool,\n    create_nakladnoy_tool,\n    create_intercompany_transfer_tool,\n    cancel_nakladnoy_tool,\n    get_product_price,\n    create_bron_tool,\n    get_pending_bron_cancel_requests_tool,\n    action_bron_cancel_request_tool,\n    save_learning_tool,\n    update_odoo_record,\n    delete_odoo_record,\n    execute_odoo_button,\n    execute_odoo_shell_command\n]"

with open(odoo_tools_path, "r", encoding="utf-8") as f:
    content = f.read()
content = content.replace(old_list, new_list)
with open(odoo_tools_path, "w", encoding="utf-8") as f:
    f.write(content)

# Now update ai_agent.py prompt
with open(ai_agent_path, "r", encoding="utf-8") as f:
    ai_content = f.read()

old_prompt_section = """            f"4. BOSHQA ISHLAR: Nakladnoy yaratish, Cancel qilish, Intercompany Transfer qilish (Transferda ham free to use tekshiring). Agar asbobingiz yetishmasa universal_odoo_search dan foydalaning.\\n\\n"
            f"DIQQAT: Siz xotiradan (pastda berilgan) o'rgangan qoidalaringizni DOIM qo'llashingiz SHART!\\n\\n\""""

new_prompt_section = """            f"4. QISMAN TAHRIRLASH (CHISTICHNO): Foydalanuvchi bron ichidagi tovarni masalan '100 kg ga kamaytir' desa, siz avval 'universal_odoo_search' orqali shu bron va uning 'sale.order.line' ini topasiz. So'ng 'update_odoo_record' orqali uning miqdorini (product_uom_qty) o'zgartirasiz. Natijada tovar 'free to use' ga qaytadi.\\n"
            f"5. NAKLADNOY BEKOR QILISH (UDALIT): Foydalanuvchi zakaz raqamini (masalan 'S39549' yoki shunchaki '39549') aytib 'udalit qil' yoki 'atmen qil' desa, avval 'sale.order' (Orders) jadvalida nomi (name) orqali izlaysiz (1C kod orqali emas!). So'ng uning ichiga kirib (execute_odoo_button orqali 'action_cancel' bosib) nakladnoyni bekor qilasiz. Keyin unga bog'langan 'stock.picking' (dostavka) hujjatini izlaysiz. Agar uning holati (state) allaqachon 'done' (Ketti qilingan) bo'lsa teginmaysiz. Agar hali 'done' bo'lmagan bo'lsa, 'delete_odoo_record' vositasi orqali shu stock.picking hujjatini TO'LIQ o'chirib (unlink) yuborasiz! Bekor qilingandan so'ng, foydalanuvchiga kulrang rangdagi 'Canceled' holatida ekanligi haqida ta'kidlab aytasiz (skrinshot tashlashni o'rniga so'z bilan tushuntirasiz, chunki sizda rasm yuborish imkoni yo'q, lekin chiroyli Markdown jadval/matn qilib bera olasiz).\\n"
            f"6. ODOO SHELL SCRIPT (execute_odoo_shell_command): Agar foydalanuvchi AYNAN 'shell orqali qilsa boladimi' yoki 'shell da yoz' desa GINA bu vositadan foydalanasiz. LAKIN DIQQAT!!! Vositaning o'zini to'g'ridan to'g'ri ishlatish qat'iyan MAN ETILADI! Avval siz foydalanuvchiga nima script yozishingizni, bu Odoo tizimida qanday o'zgarish/asorat olib kelishini qisqa-qisqa (asoratlari yomon oqibat va ijobiy hammasini) tushuntirib berasiz va eng oxirida 'Tasdiqlaysizmi?' deb G'IRt SO'RAYSIZ. Agar foydalanuvchi 'ha hamma joyda tasdiqlayman' desa GINA siz 'execute_odoo_shell_command' asbobini ishlata olasiz. Boshqa barcha holatlarda Odoo interface tugmalari (update/delete/execute_button) asboblaridan foydalanasiz.\\n\\n"
            f"DIQQAT: Siz xotiradan (pastda berilgan) o'rgangan qoidalaringizni DOIM qo'llashingiz SHART! Odoo ma'lumotlarini o'qish, yaratish va o'chirish (unlink) imkoniyatlariga (Super Bot) egasiz!\\n\\n\""""

ai_content = ai_content.replace(old_prompt_section, new_prompt_section)

with open(ai_agent_path, "w", encoding="utf-8") as f:
    f.write(ai_content)

print("Super Tools and Prompts injected successfully!")
