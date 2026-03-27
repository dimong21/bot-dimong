import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import time
import datetime
import json
import os
import re
import sys
import traceback

# ------------------- Конфигурация -------------------
USER_TOKEN = os.environ.get('VK_TOKEN', '')
PREFIX = os.environ.get('BOT_PREFIX', '!')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '7777')

try:
    ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))
except:
    ADMIN_ID = 0

if not USER_TOKEN:
    print("❌ ОШИБКА: VK_TOKEN не установлен!")
    sys.exit(1)

if ADMIN_ID == 0:
    print("❌ ОШИБКА: ADMIN_ID не установлен!")
    sys.exit(1)

SYSTEM_ADMINS = {ADMIN_ID}

print("=" * 50)
print("🤖 Страничник запускается...")
print(f"📌 Префикс: {PREFIX}")
print(f"👤 Системный администратор: {ADMIN_ID}")
print("=" * 50)

# ------------------- Инициализация VK API -------------------
try:
    vk_session = vk_api.VkApi(token=USER_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkLongPoll(vk_session, wait=25)
    print("✅ VK API инициализирован успешно")
    
    me = vk.users.get()[0]
    print(f"✅ Аккаунт: {me['first_name']} {me['last_name']} (ID: {me['id']})")
    
except Exception as e:
    print(f"❌ Ошибка инициализации: {e}")
    sys.exit(1)

# ------------------- База данных -------------------
DATA_FILE = "bot_data.json"

def load_data():
    default_data = {
        "trusted_users": [ADMIN_ID],
        "blocked_users": [],
        "prefix": PREFIX,
        "quests": [],
        "links": [],  # Простой список ссылок, без категорий
        "quest_access": {str(ADMIN_ID): "all"},
        "staff_quest": {str(ADMIN_ID): "Системный администратор"},
        "maintenance": False,
        "bot_start_time": time.time(),
        "commands_used": 0,
        "requests_count": 0,
        "ping_stats": {"total_pings": 0, "response_times": []},
        "admin_logs": []
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, value in default_data.items():
                    if key not in data:
                        data[key] = value
                return data
        except:
            return default_data
    return default_data

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

db = load_data()

# ------------------- Система ролей -------------------
ROLES = {
    "6": {"name": "Системный администратор", "level": 6, "emoji": "👑", "description": "Полный доступ"},
    "5": {"name": "Куратор отдела", "level": 5, "emoji": "🎯", "description": "Управляет отделом"},
    "4": {"name": "Наставник отдела", "level": 4, "emoji": "📚", "description": "Обучает сотрудников"},
    "3": {"name": "Руководитель отдела", "level": 3, "emoji": "📋", "description": "Управляет задачами"},
    "2": {"name": "Заместитель руководителя", "level": 2, "emoji": "📝", "description": "Помогает с квестами"},
    "1": {"name": "Сотрудник отдела", "level": 1, "emoji": "👨‍💻", "description": "Выполняет квесты"}
}

def get_user_role_level(user_id):
    if user_id in SYSTEM_ADMINS:
        return 6
    role_name = db["staff_quest"].get(str(user_id))
    for role_data in ROLES.values():
        if role_data["name"] == role_name:
            return role_data["level"]
    return 0

def get_user_role_name(user_id):
    if user_id in SYSTEM_ADMINS:
        return "Системный администратор"
    return db["staff_quest"].get(str(user_id), "Нет роли")

def get_role_emoji(level):
    for role_data in ROLES.values():
        if role_data["level"] == level:
            return role_data["emoji"]
    return "👤"

def has_permission(user_id, permission):
    if user_id in SYSTEM_ADMINS:
        return True
    return get_user_role_level(user_id) >= 1

def can_manage_user(manager_id, target_id):
    if manager_id in SYSTEM_ADMINS:
        return True
    if target_id in SYSTEM_ADMINS:
        return False
    return get_user_role_level(manager_id) > get_user_role_level(target_id)

def log_admin_action(admin_id, action, target_id=None, details=""):
    log_entry = {
        "timestamp": time.time(),
        "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "admin_id": admin_id,
        "admin_name": get_user_name(admin_id),
        "action": action,
        "target_id": target_id,
        "target_name": get_user_name(target_id) if target_id else None,
        "details": details
    }
    if "admin_logs" not in db:
        db["admin_logs"] = []
    db["admin_logs"].insert(0, log_entry)
    db["admin_logs"] = db["admin_logs"][:100]
    save_data(db)

# ------------------- Функции -------------------
def send_message(user_id, message):
    try:
        vk.messages.send(user_id=user_id, message=message, random_id=get_random_id())
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

def send_chat_message(peer_id, message):
    try:
        vk.messages.send(peer_id=peer_id, message=message, random_id=get_random_id())
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

def send_to_user(user_id, message):
    try:
        vk.messages.send(user_id=user_id, message=message, random_id=get_random_id())
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

def is_maintenance():
    return db.get("maintenance", False)

def is_trusted(user_id):
    return user_id in db["trusted_users"] or user_id in SYSTEM_ADMINS

def is_blocked(user_id):
    return user_id in db["blocked_users"]

def format_uptime():
    uptime_seconds = time.time() - db.get("bot_start_time", time.time())
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    return f"{hours} ч, {minutes} мин"

def calculate_averages():
    uptime_seconds = time.time() - db.get("bot_start_time", time.time())
    uptime_hours = uptime_seconds / 3600
    if uptime_hours == 0:
        return 0, 0
    commands = db.get("commands_used", 0)
    requests = db.get("requests_count", 0)
    return requests / uptime_hours, commands / uptime_hours

def find_user_id_from_text(text):
    mention_match = re.search(r'\[id(\d+)\|', text)
    if mention_match:
        return int(mention_match.group(1))
    id_match = re.search(r'id(\d+)', text)
    if id_match:
        return int(id_match.group(1))
    num_match = re.search(r'(\d{5,10})', text)
    if num_match:
        return int(num_match.group(1))
    return None

def get_reply_user_id(event):
    try:
        messages = vk.messages.getHistory(peer_id=event.peer_id, count=1)
        if messages.get('items'):
            last_msg = messages['items'][0]
            if last_msg.get('reply_message'):
                return last_msg['reply_message']['from_id']
    except:
        pass
    return None

def get_user_id_from_event(event, text):
    user_id = find_user_id_from_text(text)
    if user_id:
        return user_id
    user_id = get_reply_user_id(event)
    if user_id:
        return user_id
    return None

def get_user_name(user_id):
    try:
        user = vk.users.get(user_ids=user_id)
        if user:
            return f"{user[0]['first_name']} {user[0]['last_name']}"
    except:
        pass
    return f"ID{user_id}"

def get_available_links_list(user_id):
    """Получить список доступных ссылок для пользователя"""
    return db["links"]

def get_available_links(user_id):
    """Получить форматированный список доступных ссылок"""
    links = get_available_links_list(user_id)
    if not links:
        return "📭 Нет доступных ссылок"
    
    result = ""
    for i, link in enumerate(links, 1):
        result += f"{i}. {link}\n"
    return result

# ------------------- Обработка команд -------------------
def process_command(event, text, prefix):
    global db
    
    db["commands_used"] = db.get("commands_used", 0) + 1
    db["requests_count"] = db.get("requests_count", 0) + 1
    save_data(db)
    
    if is_blocked(event.user_id):
        if event.peer_id == event.user_id:
            send_message(event.user_id, "❌ Вы в черном списке")
        return
    
    if is_maintenance() and event.user_id not in SYSTEM_ADMINS:
        if event.peer_id == event.user_id:
            send_message(event.user_id, "🔧 Технические работы")
        return
    
    command_parts = text.split()
    if not command_parts:
        return
    
    command = command_parts[0].lower().replace(prefix, "")
    args = command_parts[1:] if len(command_parts) > 1 else []
    
    def reply(message_text):
        if event.peer_id != event.user_id:
            send_chat_message(event.peer_id, message_text)
        else:
            send_message(event.user_id, message_text)
    
    current_prefix = db.get("prefix", PREFIX)
    
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {event.user_id}: {command}")
    
    # ------------------- Система ссылок :links -------------------
    if command == "links":
        if get_user_role_level(event.user_id) < 1:
            reply("❌ Нет доступа к системе ссылок")
            return
        
        if len(args) < 1:
            user_level = get_user_role_level(event.user_id)
            
            result = f"🔗 **Система ссылок**\n\n👤 Ваш уровень: {user_level}\n\n"
            
            links = db["links"]
            if links:
                result += "**📋 Список ссылок:**\n"
                for i, link in enumerate(links, 1):
                    result += f"{i}. {link}\n"
            else:
                result += "📭 Нет добавленных ссылок"
            
            reply(result)
            return
        
        subcmd = args[0].lower()
        
        if subcmd == "add":
            if get_user_role_level(event.user_id) < 2:
                reply("❌ Нет прав для добавления ссылок")
                return
            
            if len(args) < 2:
                reply(f"❌ Использование: {current_prefix}links add <ссылка>")
                return
            
            link = args[1]
            
            if "links" not in db:
                db["links"] = []
            db["links"].append(link)
            
            save_data(db)
            log_admin_action(event.user_id, "link_add", None, link)
            reply(f"✅ Ссылка добавлена: {link}")
        
        elif subcmd == "remove":
            if get_user_role_level(event.user_id) < 2:
                reply("❌ Нет прав для удаления ссылок")
                return
            
            if len(args) < 2:
                reply(f"❌ Использование: {current_prefix}links remove <номер>")
                return
            
            try:
                index = int(args[1]) - 1
            except:
                reply("❌ Укажите номер ссылки")
                return
            
            if index < 0 or index >= len(db["links"]):
                reply("❌ Ссылка не найдена")
                return
            
            removed = db["links"].pop(index)
            save_data(db)
            log_admin_action(event.user_id, "link_remove", None, removed)
            reply(f"✅ Ссылка удалена: {removed}")
        
        elif subcmd == "clear":
            if get_user_role_level(event.user_id) < 6:
                reply("❌ Только системный администратор")
                return
            
            db["links"] = []
            save_data(db)
            log_admin_action(event.user_id, "link_clear")
            reply("✅ Все ссылки удалены")
        
        else:
            reply(f"""🔗 **Система ссылок**

Доступные команды:
`{current_prefix}links` - показать все ссылки
`{current_prefix}links add <ссылка>` - добавить ссылку
`{current_prefix}links remove <номер>` - удалить ссылку
`{current_prefix}links clear` - удалить все ссылки (только админ)""")
    
    # ------------------- Команда getquests -------------------
    elif command == "getquests" or command == "qgetquests":
        user_level = get_user_role_level(event.user_id)
        if user_level < 1:
            reply("❌ Нет доступа к квестам")
            return
        
        if len(args) < 1:
            links_list = get_available_links(event.user_id)
            reply(f"❌ Использование: {current_prefix}getquests <номер>\n\nДоступные ссылки:\n{links_list}")
            return
        
        try:
            link_index = int(args[0]) - 1
        except:
            reply("❌ Укажите номер ссылки из списка")
            return
        
        available_links = get_available_links_list(event.user_id)
        
        if link_index < 0 or link_index >= len(available_links):
            reply("❌ Ссылка не найдена. Используйте !links для просмотра доступных ссылок")
            return
        
        selected_link = available_links[link_index]
        
        quest_entry = {
            "user_id": event.user_id,
            "user_name": get_user_name(event.user_id),
            "link": selected_link,
            "timestamp": time.time(),
            "date": datetime.datetime.now().strftime("%d.%m.%y %H:%M")
        }
        
        if "quests" not in db:
            db["quests"] = []
        db["quests"].append(quest_entry)
        save_data(db)
        
        if event.peer_id != event.user_id:
            send_chat_message(event.peer_id, f"/getquests {selected_link}")
        else:
            reply(f"✅ Квест сохранен!\n\nСтраничник написал в чат:\n/getquests {selected_link}")
        
        log_admin_action(event.user_id, "quest_used", None, selected_link[:100])
    
    # ------------------- Основные команды -------------------
    elif command == "help":
        help_text = f"""🤖 **Страничник - помощь**

👤 **Ваша роль:** {get_user_role_name(event.user_id)} {get_role_emoji(get_user_role_level(event.user_id))}

**Основные команды:**
`{current_prefix}help` - это сообщение
`{current_prefix}ping` - статистика бота
`{current_prefix}stats` - ваша статистика
`{current_prefix}botstats` - статистика бота

**Ссылки и квесты:**
`{current_prefix}links` - просмотр ссылок
`{current_prefix}links add <ссылка>` - добавить ссылку
`{current_prefix}links remove <номер>` - удалить ссылку
`{current_prefix}getquests <номер>` - использовать ссылку

**Управление ролями:**
`{current_prefix}setrole @user <1-6>` - назначить роль

**Расшифровка цифр:**
6 👑 Системный администратор - полный доступ
5 🎯 Куратор отдела - управляет отделом
4 📚 Наставник отдела - обучает сотрудников
3 📋 Руководитель отдела - управляет задачами
2 📝 Заместитель руководителя - помогает с квестами
1 👨‍💻 Сотрудник отдела - выполняет квесты

`{current_prefix}removerole @user` - снять роль
`{current_prefix}stafflist` - список сотрудников

**Друзья:**
`{current_prefix}addfriend @user` - добавить в друзья
`{current_prefix}delfriend @user` - удалить из друзей

**Управление:**
`{current_prefix}trust @user` - добавить в доверенные
`{current_prefix}untrust @user` - удалить из доверенных

**Для администраторов:** `{current_prefix}admin`"""
        reply(help_text)
    
    elif command == "help1":
        if get_user_role_level(event.user_id) < 1:
            reply("❌ У вас нет доступа к командам отдела квестов")
            return
        
        help_text = f"""🎯 **Отдел квестов - команды:**

━━━━━━━━━━━━━━━━━━━━━
**🔗 Система ссылок:**
`{current_prefix}links` - просмотр ссылок
`{current_prefix}links add <ссылка>` - добавить ссылку
`{current_prefix}links remove <номер>` - удалить ссылку
`{current_prefix}links clear` - удалить все ссылки (админ)

━━━━━━━━━━━━━━━━━━━━━
**📋 Квесты:**
`{current_prefix}getquests <номер>` - использовать ссылку
(Страничник пишет: /getquests ссылка)

━━━━━━━━━━━━━━━━━━━━━
**👥 Управление персоналом:**
`{current_prefix}setrole @user <1-6>` - назначить роль
`{current_prefix}removerole @user` - снять роль
`{current_prefix}stafflist` - список сотрудников

━━━━━━━━━━━━━━━━━━━━━
**🎯 Роли (1-6):**
6 👑 Системный администратор - полный доступ
5 🎯 Куратор отдела - управляет отделом
4 📚 Наставник отдела - обучает сотрудников
3 📋 Руководитель отдела - управляет задачами
2 📝 Заместитель руководителя - помогает с квестами
1 👨‍💻 Сотрудник отдела - выполняет квесты"""
        reply(help_text)
    
    elif command == "ping":
        if args:
            target_id = get_user_id_from_event(event, text)
            if not target_id:
                reply("❌ Укажите пользователя")
                return
            try:
                start = time.time()
                vk.messages.send(user_id=target_id, message="🏓", random_id=get_random_id())
                end = time.time()
                ping_ms = (end - start) * 1000
                reply(f"🏓 Пинг {get_user_name(target_id)}: {ping_ms:.0f} мс")
            except:
                reply("❌ Пользователь не отвечает")
            return
        
        avg_req, avg_cmd = calculate_averages()
        uptime = format_uptime()
        
        reply(f"""🏓 **Pong!**

📊 **Статистика:**
• Время работы: {uptime}
• Всего команд: {db.get('commands_used', 0)}
• Доверенных: {len(db['trusted_users'])}
• В ЧС: {len(db['blocked_users'])}
• Квестов: {len(db.get('quests', []))}
• Ссылок: {len(db['links'])}
• Префикс: {current_prefix}""")
    
    elif command == "stats":
        user_id = event.user_id
        user_name = get_user_name(user_id)
        role_level = get_user_role_level(user_id)
        role_name = get_user_role_name(user_id)
        is_trust = "✅" if is_trusted(user_id) else "❌"
        
        user_quests = [q for q in db.get("quests", []) if q.get("user_id") == user_id]
        
        reply(f"""📊 **Ваша статистика:** {user_name}

• ID: {user_id}
• Роль: {role_name} {get_role_emoji(role_level)}
• Уровень: {role_level}
• В доверии: {is_trust}
• Квестов выполнено: {len(user_quests)}
• Всего команд: {db.get('commands_used', 0)}""")
    
    elif command == "botstats":
        avg_req, avg_cmd = calculate_averages()
        uptime = format_uptime()
        
        reply(f"""🤖 **Статистика бота**

⏱ Время работы: {uptime}
📈 Средняя нагрузка/час:
   • Запросов: {avg_req:.1f}
   • Команд: {avg_cmd:.1f}

👥 **Пользователи:**
   • Доверенных: {len(db['trusted_users'])}
   • В ЧС: {len(db['blocked_users'])}
   • Системных админов: {len(SYSTEM_ADMINS)}
   • Сотрудников: {len(db['staff_quest'])}

🔗 **Ссылки:** {len(db['links'])}
📊 **Квесты:** {len(db.get('quests', []))}
📊 Всего команд: {db.get('commands_used', 0)}""")
    
    # ------------------- Друзья -------------------
    elif command == "addfriend":
        if not is_trusted(event.user_id):
            reply("❌ Нет доступа")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        try:
            vk.friends.add(user_id=target_id)
            reply(f"✅ Запрос отправлен {get_user_name(target_id)}")
        except Exception as e:
            reply(f"❌ Ошибка: {e}")
    
    elif command == "delfriend":
        if not is_trusted(event.user_id):
            reply("❌ Нет доступа")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        try:
            vk.friends.delete(user_id=target_id)
            reply(f"✅ {get_user_name(target_id)} удален из друзей")
        except Exception as e:
            reply(f"❌ Ошибка: {e}")
    
    # ------------------- Система доверия -------------------
    elif command == "trust":
        if get_user_role_level(event.user_id) < 2:
            reply("❌ Нет прав")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id not in db["trusted_users"]:
            db["trusted_users"].append(target_id)
            save_data(db)
            log_admin_action(event.user_id, "trust_add", target_id)
            reply(f"✅ {get_user_name(target_id)} добавлен в доверенные")
        else:
            reply(f"ℹ️ Уже в доверенных")
    
    elif command == "untrust":
        if get_user_role_level(event.user_id) < 2:
            reply("❌ Нет прав")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id in db["trusted_users"]:
            db["trusted_users"].remove(target_id)
            save_data(db)
            log_admin_action(event.user_id, "trust_remove", target_id)
            reply(f"✅ {get_user_name(target_id)} удален из доверенных")
        else:
            reply(f"ℹ️ Не в доверенных")
    
    elif command == "block":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет прав")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id in SYSTEM_ADMINS:
            reply("❌ Нельзя заблокировать системного администратора")
            return
        
        if target_id not in db["blocked_users"]:
            db["blocked_users"].append(target_id)
            save_data(db)
            log_admin_action(event.user_id, "block_add", target_id)
            reply(f"✅ {get_user_name(target_id)} добавлен в ЧС")
        else:
            reply(f"ℹ️ Уже в ЧС")
    
    elif command == "unblock":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет прав")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id in db["blocked_users"]:
            db["blocked_users"].remove(target_id)
            save_data(db)
            log_admin_action(event.user_id, "block_remove", target_id)
            reply(f"✅ {get_user_name(target_id)} удален из ЧС")
        else:
            reply(f"ℹ️ Не в ЧС")
    
    # ------------------- Сообщения -------------------
    elif command == "send":
        if get_user_role_level(event.user_id) < 2:
            reply("❌ Нет прав")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите получателя")
            return
        
        msg_text = " ".join(args[1:]) if len(args) > 1 else ""
        if not msg_text:
            reply("❌ Введите текст сообщения")
            return
        
        if send_to_user(target_id, msg_text):
            log_admin_action(event.user_id, "send_message", target_id, msg_text[:100])
            reply(f"✅ Сообщение отправлено {get_user_name(target_id)}")
        else:
            reply("❌ Ошибка отправки")
    
    # ------------------- Команды отдела квестов -------------------
    elif command == "giveaccess":
        if get_user_role_level(event.user_id) < 2:
            reply("❌ Нет прав")
            return
        
        if len(args) < 2:
            reply(f"❌ Использование: {current_prefix}giveaccess @user <команда/all>")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        command_name = args[-1]
        available_commands = ["all", "getquests", "links", "help1", "stafflist", "giveaccess", "setrole"]
        
        if command_name not in available_commands:
            reply(f"❌ Доступные команды: {', '.join(available_commands)}")
            return
        
        if command_name == "all":
            db["quest_access"][str(target_id)] = "all"
        else:
            user_access = db["quest_access"].get(str(target_id), [])
            if isinstance(user_access, list):
                if command_name not in user_access:
                    user_access.append(command_name)
                    db["quest_access"][str(target_id)] = user_access
            else:
                db["quest_access"][str(target_id)] = [command_name]
        
        save_data(db)
        log_admin_action(event.user_id, "give_access", target_id, command_name)
        reply(f"✅ {get_user_name(target_id)} получил доступ к команде `{command_name}`")
    
    elif command == "removeaccess":
        if get_user_role_level(event.user_id) < 2:
            reply("❌ Нет прав")
            return
        
        if len(args) < 2:
            reply(f"❌ Использование: {current_prefix}removeaccess @user <команда>")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        command_name = args[-1]
        user_access = db["quest_access"].get(str(target_id), [])
        
        if user_access == "all":
            if command_name == "all":
                del db["quest_access"][str(target_id)]
                reply(f"✅ У {get_user_name(target_id)} удален полный доступ")
            else:
                reply("❌ У пользователя полный доступ. Используйте: !removeaccess @user all")
                return
        elif isinstance(user_access, list) and command_name in user_access:
            user_access.remove(command_name)
            if not user_access:
                del db["quest_access"][str(target_id)]
            else:
                db["quest_access"][str(target_id)] = user_access
            reply(f"✅ У {get_user_name(target_id)} удален доступ к команде `{command_name}`")
        else:
            reply(f"❌ У {get_user_name(target_id)} нет доступа к команде `{command_name}`")
            return
        
        save_data(db)
        log_admin_action(event.user_id, "remove_access", target_id, command_name)
    
    elif command == "listaccess":
        if get_user_role_level(event.user_id) < 2:
            reply("❌ Нет прав")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            target_id = event.user_id
        
        access = db["quest_access"].get(str(target_id), [])
        role_name = get_user_role_name(target_id)
        
        if access == "all":
            text_access = "🎯 Полный доступ (all)"
        elif access:
            text_access = f"🎯 Доступные команды:\n   {', '.join(access)}"
        else:
            text_access = "🎯 Нет доступа"
        
        reply(f"""📋 **Доступ пользователя {get_user_name(target_id)}**

👤 Роль: {role_name} {get_role_emoji(get_user_role_level(target_id))}
{text_access}""")
    
    elif command == "setrole":
        if get_user_role_level(event.user_id) < 3:
            reply("❌ Нет прав для назначения ролей")
            return
        
        if len(args) < 2:
            reply(f"""❌ Использование: {current_prefix}setrole @user <1-6>

**Расшифровка цифр:**
6 👑 Системный администратор - полный доступ
5 🎯 Куратор отдела - управляет отделом
4 📚 Наставник отдела - обучает сотрудников
3 📋 Руководитель отдела - управляет задачами
2 📝 Заместитель руководителя - помогает с квестами
1 👨‍💻 Сотрудник отдела - выполняет квесты

Пример: {current_prefix}setrole @user 5""")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        role_input = args[-1]
        role_map = {
            "6": "Системный администратор",
            "5": "Куратор отдела",
            "4": "Наставник отдела",
            "3": "Руководитель отдела",
            "2": "Заместитель руководителя",
            "1": "Сотрудник отдела"
        }
        
        if role_input not in role_map:
            reply(f"""❌ Неверный номер роли. Доступные роли:

6 👑 Системный администратор
5 🎯 Куратор отдела
4 📚 Наставник отдела
3 📋 Руководитель отдела
2 📝 Заместитель руководителя
1 👨‍💻 Сотрудник отдела

Использование: {current_prefix}setrole @user <1-6>""")
            return
        
        role = role_map[role_input]
        
        if target_id in SYSTEM_ADMINS and event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нельзя управлять системным администратором")
            return
        
        if not can_manage_user(event.user_id, target_id):
            reply("❌ Недостаточно прав для управления этим пользователем")
            return
        
        db["staff_quest"][str(target_id)] = role
        db["quest_access"][str(target_id)] = "all"
        
        if role == "Системный администратор":
            SYSTEM_ADMINS.add(target_id)
        
        if target_id not in db["trusted_users"]:
            db["trusted_users"].append(target_id)
        
        save_data(db)
        
        log_admin_action(event.user_id, "set_role", target_id, role)
        reply(f"✅ {get_user_name(target_id)} назначен: {role} {get_role_emoji(int(role_input))}")
    
    elif command == "removerole":
        if get_user_role_level(event.user_id) < 3:
            reply("❌ Нет прав")
            return
        
        if len(args) < 1:
            reply(f"❌ Использование: {current_prefix}removerole @user")
            return
        
        target_id = get_user_id_from_event(event, text)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id == ADMIN_ID:
            reply("❌ Нельзя снять роль с главного администратора")
            return
        
        if target_id in SYSTEM_ADMINS and event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нельзя управлять системным администратором")
            return
        
        if not can_manage_user(event.user_id, target_id):
            reply("❌ Недостаточно прав")
            return
        
        if str(target_id) in db["staff_quest"]:
            old_role = db["staff_quest"][str(target_id)]
            del db["staff_quest"][str(target_id)]
            if target_id in SYSTEM_ADMINS and target_id != ADMIN_ID:
                SYSTEM_ADMINS.remove(target_id)
            save_data(db)
            log_admin_action(event.user_id, "remove_role", target_id, old_role)
            reply(f"✅ Роль снята с {get_user_name(target_id)}")
        else:
            reply(f"ℹ️ У {get_user_name(target_id)} нет роли")
    
    elif command == "stafflist":
        if get_user_role_level(event.user_id) < 1:
            reply("❌ Нет доступа")
            return
        
        if not db["staff_quest"]:
            reply("📭 Нет сотрудников отдела")
            return
        
        result = "👥 **Сотрудники отдела:**\n\n"
        for level in range(6, 0, -1):
            role_name = ROLES[str(level)]["name"]
            members = [uid for uid, r in db["staff_quest"].items() if r == role_name]
            if members:
                result += f"**{role_name}** {get_role_emoji(level)}:\n"
                for uid in members:
                    name = get_user_name(int(uid))
                    result += f"  • {name}\n"
                result += "\n"
        
        reply(result)
    
    # ------------------- Администрирование -------------------
    elif command == "admin":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет доступа к админ-панели")
            return
        
        reply(f"""🔧 **Админ-панель**

👑 **Ваша роль:** {get_user_role_name(event.user_id)}

**Команды:**
`{current_prefix}prefix <новый>` - сменить префикс
`{current_prefix}maintenance on/off` - тех. работы
`{current_prefix}reboot` - перезагрузка
`{current_prefix}resetstats` - сброс статистики
`{current_prefix}logs` - лог действий
`{current_prefix}broadcast <текст>` - массовая рассылка

**Управление ссылками:**
`{current_prefix}links add <ссылка>` - добавить ссылку
`{current_prefix}links remove <номер>` - удалить ссылку
`{current_prefix}links clear` - удалить все ссылки

**Управление ролями:**
`{current_prefix}sysadmin add @user` - добавить системного админа
`{current_prefix}sysadmin list` - список админов

Текущий префикс: `{current_prefix}`""")
    
    elif command == "prefix":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет прав")
            return
        
        if len(args) < 1:
            reply("❌ Укажите новый префикс")
            return
        
        new_prefix = args[0]
        if len(new_prefix) > 5:
            reply("❌ Макс 5 символов")
            return
        
        db["prefix"] = new_prefix
        save_data(db)
        log_admin_action(event.user_id, "change_prefix", None, new_prefix)
        reply(f"✅ Префикс изменен на `{new_prefix}`")
    
    elif command == "maintenance":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет прав")
            return
        
        if len(args) < 1:
            reply("❌ maintenance on/off")
            return
        
        mode = args[0].lower()
        if mode == "on":
            db["maintenance"] = True
            save_data(db)
            log_admin_action(event.user_id, "maintenance_on")
            reply("🔧 Тех. работы ВКЛЮЧЕНЫ")
        elif mode == "off":
            db["maintenance"] = False
            save_data(db)
            log_admin_action(event.user_id, "maintenance_off")
            reply("✅ Тех. работы ВЫКЛЮЧЕНЫ")
        else:
            reply("❌ on или off")
    
    elif command == "reboot":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет прав")
            return
        
        reply("🔄 Перезагрузка бота...")
        save_data(db)
        sys.exit(0)
    
    elif command == "resetstats":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет прав")
            return
        
        db["commands_used"] = 0
        db["requests_count"] = 0
        db["bot_start_time"] = time.time()
        save_data(db)
        log_admin_action(event.user_id, "reset_stats")
        reply("✅ Статистика сброшена")
    
    elif command == "logs":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет прав")
            return
        
        logs = db.get("admin_logs", [])[:20]
        if not logs:
            reply("📭 Логов нет")
            return
        
        result = "📋 **Последние действия:**\n\n"
        for log in logs:
            result += f"[{log['date']}] {log['admin_name']}: {log['action']}\n"
            if log.get('target_name'):
                result += f"   → {log['target_name']}\n"
            if log.get('details'):
                result += f"   📝 {log['details']}\n"
            result += "\n"
        
        if len(result) > 4000:
            result = result[:4000] + "\n...(обрезано)"
        reply(result)
    
    elif command == "broadcast":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет прав")
            return
        
        msg_text = " ".join(args)
        if not msg_text:
            reply("❌ Введите текст рассылки")
            return
        
        sent = 0
        for uid in db["trusted_users"]:
            if send_to_user(uid, f"📢 **Рассылка:**\n{msg_text}"):
                sent += 1
            time.sleep(0.3)
        
        log_admin_action(event.user_id, "broadcast", None, f"Отправлено {sent} пользователям")
        reply(f"✅ Рассылка отправлена {sent} пользователям")
    
    elif command == "sysadmin":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Только системный администратор")
            return
        
        if len(args) < 1:
            reply(f"""🔧 **Управление системными админами:**

`{current_prefix}sysadmin add @user` - добавить
`{current_prefix}sysadmin remove @user` - удалить
`{current_prefix}sysadmin list` - список""")
            return
        
        subcmd = args[0].lower()
        
        if subcmd == "add":
            target_id = get_user_id_from_event(event, text)
            if not target_id:
                reply("❌ Укажите пользователя")
                return
            
            SYSTEM_ADMINS.add(target_id)
            db["staff_quest"][str(target_id)] = "Системный администратор"
            db["quest_access"][str(target_id)] = "all"
            if target_id not in db["trusted_users"]:
                db["trusted_users"].append(target_id)
            save_data(db)
            log_admin_action(event.user_id, "add_sysadmin", target_id)
            reply(f"✅ {get_user_name(target_id)} теперь системный администратор")
        
        elif subcmd == "remove":
            target_id = get_user_id_from_event(event, text)
            if not target_id:
                reply("❌ Укажите пользователя")
                return
            
            if target_id == ADMIN_ID:
                reply("❌ Нельзя удалить главного администратора")
                return
            
            if target_id in SYSTEM_ADMINS:
                SYSTEM_ADMINS.remove(target_id)
                log_admin_action(event.user_id, "remove_sysadmin", target_id)
                reply(f"✅ {get_user_name(target_id)} больше не системный администратор")
            else:
                reply("ℹ️ Пользователь не является системным администратором")
        
        elif subcmd == "list":
            result = "👑 **Системные администраторы:**\n\n"
            for uid in SYSTEM_ADMINS:
                result += f"• {get_user_name(uid)} (ID: {uid})\n"
            reply(result)
    
    elif command == "selfadmin":
        if event.user_id != ADMIN_ID:
            reply("❌ Только главный администратор")
            return
        
        SYSTEM_ADMINS.add(ADMIN_ID)
        db["staff_quest"][str(ADMIN_ID)] = "Системный администратор"
        db["quest_access"][str(ADMIN_ID)] = "all"
        if ADMIN_ID not in db["trusted_users"]:
            db["trusted_users"].append(ADMIN_ID)
        save_data(db)
        
        reply(f"""✅ **Вы получили полный доступ!**

👑 **Роль:** Системный администратор (уровень 6)

**Команды:**
`{current_prefix}admin` - админ-панель
`{current_prefix}help1` - отдел квестов
`{current_prefix}links` - система ссылок
`{current_prefix}links add <ссылка>` - добавить ссылку
`{current_prefix}getquests <номер>` - использовать ссылку

Префикс: `{current_prefix}`""")

# ------------------- Основной цикл -------------------
def main():
    print("=" * 50)
    print("🤖 Страничник запущен на Bothost!")
    current_prefix = db.get("prefix", PREFIX)
    print(f"📌 Префикс: {current_prefix}")
    print(f"👑 Системный администратор: {ADMIN_ID}")
    print("💬 Работает в ЛС и беседах")
    print("=" * 50)
    print("Ожидание команд...")
    
    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW:
                    if event.to_me or (event.peer_id != event.user_id):
                        message_text = event.text.strip() if event.text else ""
                        if not message_text:
                            continue
                        
                        current_prefix = db.get("prefix", PREFIX)
                        if message_text.startswith(current_prefix):
                            try:
                                process_command(event, message_text, current_prefix)
                            except Exception as e:
                                print(f"Ошибка: {e}")
                                traceback.print_exc()
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
