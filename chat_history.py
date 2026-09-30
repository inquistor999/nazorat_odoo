"""
chat_history.py — Barcha foydalanuvchilar suhbatini timestamp bilan doimiy saqlovchi modul.

ARXITEKTURA:
- Har bir kiruvchi xabar BOT JAVOB BERMASDAN OLDIN darhol saqlanadi.
- Bot javobi kelgandan keyin shu yozuvga qo'shib yangilanadi.
- Foydalanuvchi xabarini o'chirib yuborganida ham bot tarixida qoladi.
- Har bir user uchun oxirgi 2000 ta yozuv (juft: user xabari + bot javobi) saqlanadi.
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


def log_incoming(user_id: int, username: str, odoo_manager: str, user_text: str) -> str:
    """
    Foydalanuvchi xabari KELGAN ZAHOTI (bot javob bermasdan oldin) darhol saqlanadi.
    O'chirilgan xabarlar ham shu yerda qoladi.
    
    Returns:
        msg_id — bu yozuvning unikal identifikatori (keyinroq bot javobi qo'shish uchun).
    """
    history = load_history()
    uid = str(user_id)
    
    if uid not in history:
        history[uid] = {
            'username': username,
            'odoo_manager': odoo_manager,
            'messages': []
        }
    
    history[uid]['username'] = username
    if odoo_manager:
        history[uid]['odoo_manager'] = odoo_manager

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg_id = f"{uid}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    history[uid]['messages'].append({
        'id': msg_id,
        'time': now_str,
        'user': user_text[:3000] if user_text else '',
        'bot': '',       # Hozircha bo'sh — bot javob bergandan keyin to'ldiriladi
        'deleted': False  # Foydalanuvchi o'chirsa ham bu False bo'lib qoladi (biz saqlaganmiz!)
    })

    # Hajm chegarasi: oxirgi 2000 ta yozuv
    if len(history[uid]['messages']) > 2000:
        history[uid]['messages'] = history[uid]['messages'][-2000:]

    save_history(history)
    return msg_id


def update_bot_reply(user_id: int, msg_id: str, bot_reply: str):
    """
    log_incoming orqali saqlangan yozuvga bot javobini qo'shib yangilaydi.
    msg_id — log_incoming qaytargan identifikator.
    """
    history = load_history()
    uid = str(user_id)
    
    if uid not in history:
        return
    
    messages = history[uid]['messages']
    # Oxiridan boshlab izlaymiz (yangi yozuvlar oxirida)
    for i in range(len(messages) - 1, max(len(messages) - 20, -1), -1):
        if messages[i].get('id') == msg_id:
            messages[i]['bot'] = bot_reply[:3000] if bot_reply else ''
            save_history(history)
            return
    
    # Agar msg_id topilmasa (eski format), oxirgi yozuvga qo'shamiz
    if messages and not messages[-1].get('bot'):
        messages[-1]['bot'] = bot_reply[:3000] if bot_reply else ''
        save_history(history)


def add_message(user_id: int, username: str, odoo_manager: str, user_text: str, bot_reply: str):
    """
    Eski interfeys — hali ham ishlaydi.
    Bir vaqtda user va bot xabarini saqlaydi.
    """
    history = load_history()
    uid = str(user_id)
    
    if uid not in history:
        history[uid] = {
            'username': username,
            'odoo_manager': odoo_manager,
            'messages': []
        }
    
    history[uid]['username'] = username
    if odoo_manager:
        history[uid]['odoo_manager'] = odoo_manager

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg_id = f"{uid}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    history[uid]['messages'].append({
        'id': msg_id,
        'time': now_str,
        'user': user_text[:3000] if user_text else '',
        'bot': bot_reply[:3000] if bot_reply else '',
        'deleted': False
    })

    if len(history[uid]['messages']) > 2000:
        history[uid]['messages'] = history[uid]['messages'][-2000:]

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
        return messages[-20:]

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
    1-usul: chat_history.json dan qidiradi
    2-usul: allowed_users.json dan qidiradi (fallback)

    Returns:
        (user_id_str, username, odoo_manager) yoki (None, None, None)
    """
    manager_name_lower = manager_name.lower().strip()

    # 1. chat_history.json
    history = load_history()
    for uid, info in history.items():
        mgr = info.get('odoo_manager', '') or ''
        if manager_name_lower in mgr.lower():
            return uid, info.get('username', 'Noma\'lum'), mgr

    # 2. allowed_users.json fallback
    try:
        au_file = 'allowed_users.json'
        if os.path.exists(au_file):
            with open(au_file, 'r', encoding='utf-8') as f:
                allowed = json.load(f)
            for uid, info in allowed.items():
                mgr = info.get('odoo_manager', '') or ''
                if manager_name_lower in mgr.lower():
                    uname = info.get('username', 'Noma\'lum')
                    return uid, uname, mgr
    except Exception:
        pass

    return None, None, None


def format_history_for_admin(messages: list, username: str, odoo_manager: str, minutes: int) -> str:
    """Tarixni admin uchun chiroyli matnga aylantiradi."""
    if not messages:
        return f"❌ {odoo_manager or username} bilan oxirgi {minutes} daqiqada hech qanday suhbat topilmadi."

    lines = [
        f"🕵️ <b>Nazorat kamerasi</b> — {odoo_manager or username}\n"
        f"⏱ Oxirgi {minutes} daqiqalik suhbat ({len(messages)} ta xabar):\n"
    ]

    for msg in messages:
        time_str = msg.get('time', '')
        user_txt = msg.get('user', '')
        bot_txt = msg.get('bot', '')

        if user_txt:
            lines.append(f"🕐 <i>{time_str}</i>\n👤 <b>{odoo_manager or username}:</b> {user_txt}")
        if bot_txt:
            short_bot = bot_txt if len(bot_txt) <= 400 else bot_txt[:400] + '...'
            lines.append(f"🤖 <b>Bot:</b> {short_bot}\n")
        elif user_txt and not bot_txt:
            lines.append(f"🤖 <b>Bot:</b> <i>(javob hali yo'q yoki rasm/ovoz)</i>\n")

    return '\n'.join(lines)
