import re
content = open('odoo_tools.py', 'r', encoding='utf-8').read()
match = re.search(r'odoo_tools_list\s*=\s*\[.*?\]', content, re.DOTALL)
if match:
    list_code = match.group(0)
    content = content.replace(list_code, '') + '\n\n' + list_code
    open('odoo_tools.py', 'w', encoding='utf-8').write(content)
    print("Moved list to bottom")
