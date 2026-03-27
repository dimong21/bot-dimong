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

# Системные администраторы (полный контроль над ботом)
SYSTEM_ADMINS = {ADMIN_ID}  # Главный системный администратор

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
        "quests": {},
        "quest_access": {
            str(ADMIN_ID): "all"
        },
        "staff_quest": {
            str(ADMIN_ID): "Системный администратор"
        },
        "maintenance": False,
        "bot_start_time": time.time(),
        "commands_used": 0,
        "requests_count": 0,
        "ping_stats": {"total_pings": 0, "response_times": []},
        "admin_logs": []  # Логи действий админов
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

# ------------------- Система ролей (уровни от 1 до 6) -------------------
ROLES = {
    "6": {
        "name": "Системный администратор",
        "level": 6,
        "permissions": ["all", "admin_panel", "system_control", "manage_roles", "manage_staff", "manage_trust", "manage_block", "send_messages", "quest_commands", "view_stats"],
        "description": "👑 Полный контроль над ботом, может управлять всеми"
    },
    "5": {
        "name": "Куратор отдела",
        "level": 5,
        "permissions": ["all", "manage_roles", "manage_staff", "manage_trust", "manage_block", "send_messages", "quest_commands", "view_stats"],
        "description": "🎯 Управляет отделом квестов, назначает роли до 4 уровня"
    },
    "4": {
        "name": "Наставник отдела",
        "level": 4,
        "permissions": ["manage_staff", "manage_trust", "send_messages", "quest_commands", "view_stats"],
        "description": "📚 Обучает сотрудников, управляет доступом"
    },
    "3": {
        "name": "Руководитель отдела",
        "level": 3,
        "permissions": ["manage_staff", "manage_trust", "quest_commands", "view_stats"],
        "description": "📋 Управляет задачами и сотрудниками"
    },
    "2": {
        "name": "Заместитель руководителя",
        "level": 2,
        "permissions": ["quest_commands", "view_stats"],
        "description": "📝 Помогает с квестами и статистикой"
    },
    "1": {
        "name": "Сотрудник отдела",
        "level": 1,
        "permissions": ["quest_commands"],
        "description": "👨‍💻 Выполняет квесты"
    }
}

def get_user_role_level(user_id):
    """Получить уровень роли пользователя"""
    if user_id in SYSTEM_ADMINS:
        return 6
    role_name = db["staff_quest"].get(str(user_id))
    for role_data in ROLES.values():
        if role_data["name"] == role_name:
            return role_data["level"]
    return 0

def get_user_role_name(user_id):
    """Получить название роли пользователя"""
    if user_id in SYSTEM_ADMINS:
        return "Системный администратор"
    return db["staff_quest"].get(str(user_id), "Нет роли")

def has_permission(user_id, permission):
    """Проверка наличия разрешения у пользователя"""
    if user_id in SYSTEM_ADMINS:
        return True
    
    role_name = db["staff_quest"].get(str(user_id))
    if not role_name:
        return False
    
    for role_data in ROLES.values():
        if role_data["name"] == role_name:
            if "all" in role_data["permissions"]:
                return True
            return permission in role_data["permissions"]
    return False

def can_manage_user(manager_id, target_id):
    """Может ли manager управлять target"""
    if manager_id in SYSTEM_ADMINS:
        return True
    if target_id in SYSTEM_ADMINS:
        return False
    
    manager_level = get_user_role_level(manager_id)
    target_level = get_user_role_level(target_id)
    return manager_level > target_level and manager_id != target_id

def log_admin_action(admin_id, action, target_id=None, details=""):
    """Логирование действий админов"""
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
    # Оставляем только последние 100 логов
    db["admin_logs"] = db["admin_logs"][:100]
    save_data(db)

# ------------------- Функции -------------------
def send_message(user_id, message):
    try:
        vk.messages.send(user_id=user_id, message=message, random_id=get_random_id())
        return True
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False

def send_chat_message(peer_id, message):
    try:
        vk.messages.send(peer_id=peer_id, message=message, random_id=get_random_id())
        return True
    except Exception as e:
        print(f"Ошибка отправки: {e}")
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
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)
    
    if days > 0:
        return f"{days} дн, {hours} ч, {minutes} мин, {seconds} сек"
    return f"{hours} ч, {minutes} мин, {seconds} сек"

def calculate_averages():
    uptime_seconds = time.time() - db.get("bot_start_time", time.time())
    uptime_hours = uptime_seconds / 3600
    
    if uptime_hours == 0:
        return 0, 0
    
    commands = db.get("commands_used", 0)
    requests = db.get("requests_count", 0)
    
    avg_commands = commands / uptime_hours
    avg_requests = requests / uptime_hours
    
    return avg_requests, avg_commands

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

def get_role_emoji(level):
    emojis = {
        6: "👑",
        5: "🎯",
        4: "📚",
        3: "📋",
        2: "📝",
        1: "👨‍💻",
        0: "👤"
    }
    return emojis.get(level, "👤")

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
    
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {event.user_id}: {command}")
    
    # ------------------- Системные команды (только для системных админов) -------------------
    if command == "sysadmin":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Только системный администратор")
            return
        
        if len(args) < 1:
            reply("""🔧 **Системное администрирование**

`!sysadmin add @user` - добавить системного админа
`!sysadmin remove @user` - удалить системного админа
`!sysadmin list` - список системных админов
`!sysadmin logs` - логи действий""")
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
        
        elif subcmd == "logs":
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
    
    # ------------------- Админ-панель -------------------
    elif command == "admin":
        if not has_permission(event.user_id, "admin_panel") and event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет доступа к админ-панели")
            return
        
        if len(args) < 1:
            admin_text = f"""🔧 **Админ-панель**

👑 **Ваша роль:** {get_user_role_name(event.user_id)}
📊 **Уровень:** {get_user_role_level(event.user_id)}

**Доступные команды:**

**Управление ролями:**
`!role add @user <1-6>` - назначить роль
`!role remove @user` - снять роль
`!role list` - список всех ролей
`!role info @user` - информация о роли

**Управление доступом:**
`!trust @user` - добавить в доверенные
`!untrust @user` - удалить из доверенных
`!block @user` - добавить в ЧС
`!unblock @user` - удалить из ЧС

**Системные:**
`!prefix <новый>` - сменить префикс
`!maintenance on/off` - тех. работы
`!reboot` - перезагрузка бота
`!resetstats` - сброс статистики
`!logs` - последние действия

**Сообщения:**
`!send @user <текст>` - отправить сообщение
`!broadcast <текст>` - массовая рассылка

**Квесты:**
`!getquests <текст>` - сохранить квест
`!quests <дата>` - квесты за дату
`!stafflist` - список сотрудников

**Текущий префикс:** `{db.get('prefix', PREFIX)}`"""
            reply(admin_text)
            return
        
        subcmd = args[0].lower()
        
        if subcmd == "password" and len(args) > 1:
            if event.user_id not in SYSTEM_ADMINS:
                reply("❌ Только системный администратор")
                return
            new_password = args[1]
            db["admin_password"] = new_password
            save_data(db)
            reply("✅ Пароль изменен")
    
    # ------------------- Управление ролями -------------------
    elif command == "role":
        if not has_permission(event.user_id, "manage_roles") and event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет прав для управления ролями")
            return
        
        if len(args) < 1:
            reply("""🎯 **Управление ролями:**

`!role add @user <1-6>` - назначить роль
`!role remove @user` - снять роль
`!role list` - список ролей
`!role info @user` - информация о роли

**Доступные роли:**
6 - Системный администратор (👑)
5 - Куратор отдела (🎯)
4 - Наставник отдела (📚)
3 - Руководитель отдела (📋)
2 - Заместитель руководителя (📝)
1 - Сотрудник отдела (👨‍💻)""")
            return
        
        subcmd = args[0].lower()
        
        if subcmd == "add":
            if len(args) < 2:
                reply("❌ Использование: !role add @user <1-6>")
                return
            
            target_id = get_user_id_from_event(event, text)
            if not target_id:
                reply("❌ Укажите пользователя")
                return
            
            role_level = args[-1]
            if role_level not in ROLES:
                reply("❌ Доступные уровни: 1, 2, 3, 4, 5, 6")
                return
            
            # Проверка прав
            if target_id in SYSTEM_ADMINS and event.user_id not in SYSTEM_ADMINS:
                reply("❌ Нельзя управлять системным администратором")
                return
            
            if not can_manage_user(event.user_id, target_id):
                reply("❌ Недостаточно прав для управления этим пользователем")
                return
            
            role_name = ROLES[role_level]["name"]
            db["staff_quest"][str(target_id)] = role_name
            db["quest_access"][str(target_id)] = "all"
            
            if role_level == "6":
                SYSTEM_ADMINS.add(target_id)
            
            if target_id not in db["trusted_users"]:
                db["trusted_users"].append(target_id)
            
            save_data(db)
            log_admin_action(event.user_id, "role_add", target_id, f"Роль: {role_name}")
            reply(f"✅ {get_user_name(target_id)} назначен: {role_name} {get_role_emoji(int(role_level))}")
        
        elif subcmd == "remove":
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
                del db["staff_quest"][str(target_id)]
                if target_id in SYSTEM_ADMINS and target_id != ADMIN_ID:
                    SYSTEM_ADMINS.remove(target_id)
                save_data(db)
                log_admin_action(event.user_id, "role_remove", target_id)
                reply(f"✅ Роль снята с {get_user_name(target_id)}")
            else:
                reply(f"ℹ️ У {get_user_name(target_id)} нет роли")
        
        elif subcmd == "list":
            result = "🎯 **Система ролей:**\n\n"
            for level, role_data in sorted(ROLES.items(), reverse=True):
                result += f"**{level} - {role_data['name']}** {get_role_emoji(int(level))}\n"
                result += f"   {role_data['description']}\n\n"
            reply(result)
        
        elif subcmd == "info":
            target_id = get_user_id_from_event(event, text)
            if not target_id:
                target_id = event.user_id
            
            role_level = get_user_role_level(target_id)
            role_name = get_user_role_name(target_id)
            
            if role_level == 0:
                reply(f"👤 **{get_user_name(target_id)}**\nНет роли")
            else:
                role_data = ROLES[str(role_level)]
                result = f"""{get_role_emoji(role_level)} **Информация о пользователе:**

**Пользователь:** {get_user_name(target_id)}
**Роль:** {role_name}
**Уровень:** {role_level}
**Описание:** {role_data['description']}

**Права:**
"""
                for perm in role_data['permissions']:
                    perm_name = {
                        "all": "✓ Полный доступ",
                        "admin_panel": "✓ Админ-панель",
                        "system_control": "✓ Управление системой",
                        "manage_roles": "✓ Управление ролями",
                        "manage_staff": "✓ Управление персоналом",
                        "manage_trust": "✓ Управление доверием",
                        "manage_block": "✓ Управление ЧС",
                        "send_messages": "✓ Отправка сообщений",
                        "quest_commands": "✓ Команды квестов",
                        "view_stats": "✓ Просмотр статистики"
                    }.get(perm, f"✓ {perm}")
                    result += f"  • {perm_name}\n"
                
                reply(result)
    
    # ------------------- Основные команды -------------------
    elif command == "help":
        help_text = f"""🤖 **Страничник - помощь**

👤 **Ваша роль:** {get_user_role_name(event.user_id)} {get_role_emoji(get_user_role_level(event.user_id))}

**Основные команды:**
`!help` - это сообщение
`!ping` - статистика бота
`!stats` - ваша статистика
`!botstats` - статистика бота

**Квесты:**
`!getquests <текст>` - сохранить квест
`!quests <дата>` - квесты за дату

**Друзья:**
`!addfriend @user` - добавить в друзья
`!delfriend @user` - удалить из друзей

**Сообщения:**
`!send @user <текст>` - отправить сообщение

**Управление:**
`!trust @user` - добавить в доверенные
`!untrust @user` - удалить из доверенных

**Для администраторов:** `!admin`"""
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
• Сотрудников: {len(db['staff_quest'])}
• Префикс: {db.get('prefix', PREFIX)}""")
    
    elif command == "stats":
        user_id = event.user_id
        user_name = get_user_name(user_id)
        role_level = get_user_role_level(user_id)
        role_name = get_user_role_name(user_id)
        is_trust = "✅" if is_trusted(user_id) else "❌"
        
        reply(f"""📊 **Ваша статистика:** {user_name}

• ID: {user_id}
• Роль: {role_name} {get_role_emoji(role_level)}
• Уровень: {role_level}
• В доверии: {is_trust}
• Всего команд: {db.get('commands_used', 0)}""")
    
    elif command == "botstats":
        avg_req, avg_cmd = calculate_averages()
        uptime = format_uptime()
        
        # Статистика по ролям
        role_stats = {}
        for role_data in ROLES.values():
            role_stats[role_data["name"]] = 0
        for uid, role in db["staff_quest"].items():
            if role in role_stats:
                role_stats[role] += 1
        
        stats_text = f"""🤖 **Статистика бота**

⏱ Время работы: {uptime}
📈 Средняя нагрузка/час:
   • Запросов: {avg_req:.1f}
   • Команд: {avg_cmd:.1f}

👥 **Пользователи:**
   • Доверенных: {len(db['trusted_users'])}
   • В ЧС: {len(db['blocked_users'])}
   • Системных админов: {len(SYSTEM_ADMINS)}

🎯 **Сотрудники отдела:**
"""
        for role_name, count in role_stats.items():
            if count > 0:
                stats_text += f"   • {role_name}: {count}\n"
        
        stats_text += f"\n📊 Всего команд: {db.get('commands_used', 0)}"
        reply(stats_text)
    
    # ------------------- Сообщения -------------------
    elif command == "send":
        if not has_permission(event.user_id, "send_messages") and event.user_id not in SYSTEM_ADMINS:
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
    
    elif command == "broadcast":
        if event.user_id not in SYSTEM_ADMINS:
            reply("❌ Только системный администратор")
            return
        
        msg_text = " ".join(args)
        if not msg_text:
            reply("❌ Введите текст рассылки")
            return
        
        # Рассылка доверенным пользователям
        sent = 0
        for uid in db["trusted_users"]:
            if send_to_user(uid, f"📢 **Рассылка:**\n{msg_text}"):
                sent += 1
            time.sleep(0.5)  # Защита от флуда
        
        log_admin_action(event.user_id, "broadcast", None, f"Отправлено {sent} пользователям")
        reply(f"✅ Рассылка отправлена {sent} пользователям")
    
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
    
    # ------------------- Система доверия и ЧС -------------------
    elif command == "trust":
        if not has_permission(event.user_id, "manage_trust") and event.user_id not in SYSTEM_ADMINS:
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
        if not has_permission(event.user_id, "manage_trust") and event.user_id not in SYSTEM_ADMINS:
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
        if not has_permission(event.user_id, "manage_block") and event.user_id not in SYSTEM_ADMINS:
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
        if not has_permission(event.user_id, "manage_block") and event.user_id not in SYSTEM_ADMINS:
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
    
    # ------------------- Квесты -------------------
    elif command == "getquests":
        if not has_permission(event.user_id, "quest_commands") and event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет доступа к квестам")
            return
        
        quest_text = " ".join(args)
        if not quest_text:
            reply("❌ Введите текст квеста")
            return
        
        today = datetime.datetime.now().strftime("%d.%m.%y")
        if today not in db["quests"]:
            db["quests"][today] = []
        
        db["quests"][today].append({
            "user_id": event.user_id,
            "user_name": get_user_name(event.user_id),
            "text": quest_text,
            "timestamp": time.time()
        })
        save_data(db)
        
        if event.peer_id != event.user_id:
            send_chat_message(event.peer_id, f"📝 Квест от {get_user_name(event.user_id)}:\n{quest_text}")
        else:
            reply(f"✅ Квест сохранен за {today}")
    
    elif command == "quests":
        if not has_permission(event.user_id, "quest_commands") and event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет доступа")
            return
        
        date = args[0] if args else ""
        if not date:
            reply("❌ Укажите дату (ДД.ММ.ГГ)")
            return
        
        if not re.match(r"\d{2}\.\d{2}\.\d{2}", date):
            reply("❌ Неверный формат. Пример: 22.05.26")
            return
        
        quests = db["quests"].get(date, [])
        if not quests:
            reply(f"📭 Нет квестов за {date}")
            return
        
        result = f"📋 **Квесты за {date}:**\n\n"
        for i, q in enumerate(quests, 1):
            result += f"{i}. {q['user_name']}\n   {q['text']}\n\n"
        
        if len(result) > 4000:
            result = result[:4000] + "\n...(обрезано)"
        reply(result)
    
    # ------------------- Список сотрудников -------------------
    elif command == "stafflist":
        if not has_permission(event.user_id, "view_stats") and event.user_id not in SYSTEM_ADMINS:
            reply("❌ Нет доступа")
            return
        
        if not db["staff_quest"]:
            reply("📭 Нет сотрудников")
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
    
    # ------------------- Системные команды -------------------
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
        reply(f"✅ Префикс: `{new_prefix}`")
    
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
        db["ping_stats"] = {"total_pings": 0, "response_times": []}
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
        reply("""✅ **Вы получили полный доступ!**

👑 **Ваша роль:** Системный администратор (уровень 6)

**Доступные команды:**
• `!admin` - админ-панель
• `!role add @user <1-6>` - назначить роль
• `!sysadmin add @user` - добавить системного админа
• `!broadcast <текст>` - массовая рассылка
• `!logs` - просмотр логов

**Система ролей:**
6 👑 Системный администратор
5 🎯 Куратор отдела
4 📚 Наставник отдела
3 📋 Руководитель отдела
2 📝 Заместитель руководителя
1 👨‍💻 Сотрудник отдела""")

# ------------------- Основной цикл -------------------
def main():
    print("=" * 50)
    print("🤖 Страничник запущен на Bothost!")
    print(f"📌 Префикс: {db.get('prefix', PREFIX)}")
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
