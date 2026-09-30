"""
chat_history.py — Barcha foydalanuvchilar suhbatini timestamp bilan doimiy saqlovchi modul.
Har bir xabar saqlanadi: kim yozdi, qachon, nima dedi va bot nima javob berdi.
"""
import os
import json
import threading
from datetime import datetime

HISTORY_FILE = 'chat_history.json'
_lock = threading.Lock()


def load_history() -> dict:
    """Barcha tarixni fayldan yuklaydi."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(history: dict):
    """Tarixni faylga saqlaydi (thread-safe)."""
    with _lock:
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def add_message(user_id: int, username: str, odoo_manager: str, user_text: str, bot_reply: str):
    """
    Bitta suhbat qatnashuvini tarixga qo'shadi.
    
    Args:
        user_id: Telegram user ID
        username: Telegram first name
        odoo_manager: Odoo dagi menejer ismi (agar bo'lsa)
        user_text: Foydalanuvchi yozgan xabar
        bot_reply: Bot javob bergan matn
    """
    history = load_history()
    uid = str(user_id)
    if uid not in history:
        history[uid] = {
            'username': username,
            'odoo_manager': odoo_manager,
            'messages': []
        }
    
    # Yangilanishlarda username va manager ham yangilansin
    history[uid]['username'] = username
    history[uid]['odoo_manager'] = odoo_manager
    
    # Timestamp — ISO format (UTC +5)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    history[uid]['messages'].append({
        'time': now_str,
        'user': user_text[:2000] if user_text else '',
        'bot': bot_reply[:2000] if bot_reply else ''
    })
    
    # Xotira hajmini cheklaymiz: har bir user uchun oxirgi 500 ta xabar
    if len(history[uid]['messages']) > 500:
        history[uid]['messages'] = history[uid]['messages'][-500:]
    
    save_history(history)


def get_last_n_minutes(user_id: int, minutes: int) -> list:
    """
    Foydalanuvchining oxirgi N minutlik suhbatini qaytaradi.
    Muhim: N minut HOZIRGI vaqtdan emas, OXIRGI XABARDAN orqaga sanab boradi.
    
    Returns:
        [{'time': ..., 'user': ..., 'bot': ...}, ...]
    """
    history = load_history()
    uid = str(user_id)
    if uid not in history or not history[uid].get('messages'):
        return []
    
    messages = history[uid]['messages']
    if not messages:
        return []
    
    # Oxirgi xabarning vaqtini topamiz
    last_msg_time_str = messages[-1]['time']
    try:
        last_time = datetime.strptime(last_msg_time_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return messages[-20:]  # fallback
    
    # N minut orqaga
    from datetime import timedelta
    cutoff_time = last_time - timedelta(minutes=minutes)
    
    result = []
    for msg in messages:
        try:
            msg_time = datetime.strptime(msg['time'], '%Y-%m-%d %H:%M:%S')
            if msg_time >= cutoff_time:
                result.append(msg)
        except Exception:
            continue
    
    return result


def find_user_by_manager_name(manager_name: str) -> tuple:
    """
    Odoo menejer ismi bo'yicha user_id va username ni topadi.
    
    Returns:
        (user_id_str, username, odoo_manager) yoki (None, None, None)
    """
    history = load_history()
    manager_name_lower = manager_name.lower().strip()
    
    for uid, info in history.items():
        mgr = info.get('odoo_manager', '') or ''
        if manager_name_lower in mgr.lower():
            return uid, info.get('username', 'Noma\'lum'), mgr
    
    return None, None, None


def format_history_for_admin(messages: list, username: str, odoo_manager: str, minutes: int) -> str:
    """Tarixni admin uchun chiroyli matnga aylantiradi."""
    if not messages:
        return f"❌ {odoo_manager or username} bilan oxirgi {minutes} daqiqada hech qanday suhbat topilmadi."
    
    lines = [f"🕵️ <b>Nazorat kamerasi</b> — {odoo_manager or username}\n"
             f"⏱ Oxirgi {minutes} daqiqalik suhbat ({len(messages)} ta xabar):\n"]
    
    for msg in messages:
        time_str = msg.get('time', '')
        user_txt = msg.get('user', '')
        bot_txt = msg.get('bot', '')
        
        if user_txt:
            lines.append(f"🕐 <i>{time_str}</i>\n👤 <b>{odoo_manager or username}:</b> {user_txt}")
        if bot_txt:
            short_bot = bot_txt if len(bot_txt) <= 300 else bot_txt[:300] + '...'
            lines.append(f"🤖 <b>Bot:</b> {short_bot}\n")
    
    return '\n'.join(lines)
