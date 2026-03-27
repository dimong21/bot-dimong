import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import time
import datetime
import json
import os
import re
import traceback
import sys

# ------------------- Конфигурация -------------------
# Берем переменные из окружения (для Bothost)
USER_TOKEN = os.environ.get('VK_TOKEN', '')
PREFIX = os.environ.get('BOT_PREFIX', '!')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '7777')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))

# Проверка наличия обязательных переменных
if not USER_TOKEN:
    print("❌ ОШИБКА: VK_TOKEN не установлен!")
    print("Добавьте переменную окружения VK_TOKEN в настройках бота на Bothost")
    sys.exit(1)

if ADMIN_ID == 0:
    print("❌ ОШИБКА: ADMIN_ID не установлен!")
    print("Добавьте переменную окружения ADMIN_ID в настройках бота на Bothost")
    sys.exit(1)

TECH_ADMINS = {ADMIN_ID}

print("=" * 50)
print("🤖 Страничник запускается на Bothost...")
print(f"📌 Префикс: {PREFIX}")
print(f"👤 Ваш ID: {ADMIN_ID}")
print("=" * 50)

# ------------------- Инициализация VK API -------------------
try:
    vk_session = vk_api.VkApi(token=USER_TOKEN)
    vk = vk_session.get_api()
    # Важно: для бесед используем longpoll с правильными параметрами
    longpoll = VkLongPoll(vk_session, wait=25)
    print("✅ VK API инициализирован успешно")
    
    # Получаем информацию о своем аккаунте
    me = vk.users.get()[0]
    print(f"✅ Аккаунт: {me['first_name']} {me['last_name']} (ID: {me['id']})")
    
    # Проверяем доступ к беседам
    try:
        # Получаем список бесед для проверки
        conversations = vk.messages.getConversations(count=5)
        print(f"✅ Доступ к беседам есть")
    except Exception as e:
        print(f"⚠️ Предупреждение: возможно ограничен доступ к беседам: {e}")
    
except Exception as e:
    print(f"❌ Ошибка инициализации VK API: {e}")
    traceback.print_exc()
    sys.exit(1)

# ------------------- Базы данных (JSON) -------------------
DATA_FILE = "bot_data.json"

def load_data():
    default_data = {
        "trusted_users": [],
        "blocked_users": [],
        "prefix": PREFIX,
        "quests": {},
        "quest_access": {},
        "staff_quest": {},
        "maintenance": False,
        "bot_start_time": time.time(),
        "commands_used": 0,
        "requests_count": 0,
        "ping_stats": {
            "total_pings": 0,
            "response_times": []
        }
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, value in default_data.items():
                    if key not in data:
                        data[key] = value
                return data
        except Exception as e:
            print(f"Ошибка загрузки данных: {e}")
            return default_data
    return default_data

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения данных: {e}")

db = load_data()

# ------------------- Вспомогательные функции -------------------
def send_message(user_id, message, attachment=None):
    """Отправка сообщения в личку"""
    try:
        vk.messages.send(
            user_id=user_id,
            message=message,
            random_id=get_random_id(),
            attachment=attachment
        )
        return True
    except Exception as e:
        print(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        return False

def send_chat_message(peer_id, message, attachment=None):
    """Отправка сообщения в беседу"""
    try:
        vk.messages.send(
            peer_id=peer_id,
            message=message,
            random_id=get_random_id(),
            attachment=attachment
        )
        return True
    except Exception as e:
        print(f"Ошибка отправки сообщения в беседу {peer_id}: {e}")
        return False

def is_maintenance():
    return db.get("maintenance", False)

def is_trusted(user_id: int) -> bool:
    return user_id in db["trusted_users"] or user_id in TECH_ADMINS or user_id == ADMIN_ID

def is_blocked(user_id: int) -> bool:
    return user_id in db["blocked_users"]

def get_staff_role(user_id: int):
    return db["staff_quest"].get(str(user_id))

def is_quest_staff(user_id: int) -> bool:
    return str(user_id) in db["staff_quest"]

def get_highest_role(user_id: int) -> int:
    roles = {
        "Куратор отдела": 4,
        "Наставник отдела": 3,
        "Руководитель отдела": 2,
        "Заместитель руководителя отдела": 1
    }
    role = get_staff_role(user_id)
    return roles.get(role, 0)

def can_manage_staff(manager_id: int, target_id: int) -> bool:
    manager_role = get_highest_role(manager_id)
    target_role = get_highest_role(target_id)
    if get_staff_role(manager_id) == "Куратор отдела":
        return manager_role > target_role
    return manager_role > target_role and target_id != manager_id

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

def calculate_ping_stats():
    ping_data = db.get("ping_stats", {})
    response_times = ping_data.get("response_times", [])
    
    if not response_times:
        return {
            "avg": 0,
            "min": 0,
            "max": 0,
            "total": 0
        }
    
    return {
        "avg": sum(response_times) / len(response_times),
        "min": min(response_times),
        "max": max(response_times),
        "total": len(response_times)
    }

def find_user_id_from_text(text, peer_id, reply_message=None):
    """Извлекает ID пользователя из текста, реплая или упоминания"""
    if reply_message:
        return reply_message.get('from_id')
    
    mention_match = re.search(r'\[id(\d+)\|', text)
    if mention_match:
        return int(mention_match.group(1))
    
    id_match = re.search(r'id(\d+)', text)
    if id_match:
        return int(id_match.group(1))
    
    return None

def get_user_name(user_id):
    try:
        user = vk.users.get(user_ids=user_id, fields=['first_name', 'last_name'])
        if user:
            return f"{user[0]['first_name']} {user[0]['last_name']}"
    except:
        pass
    return f"ID{user_id}"

def get_chat_name(peer_id):
    try:
        if peer_id > 2000000000:
            chat = vk.messages.getChat(chat_id=peer_id - 2000000000)
            return chat.get('title', 'Беседа')
    except:
        pass
    return "Беседа"

# ------------------- Система пинга -------------------
def ping_user(user_id):
    try:
        start_time = time.time()
        
        sent_message = vk.messages.send(
            user_id=user_id,
            message="🏓 Пинг!",
            random_id=get_random_id()
        )
        
        end_time = time.time()
        response_time = (end_time - start_time) * 1000
        
        ping_stats = db.get("ping_stats", {})
        if "response_times" not in ping_stats:
            ping_stats["response_times"] = []
        
        ping_stats["response_times"].append(response_time)
        if len(ping_stats["response_times"]) > 100:
            ping_stats["response_times"] = ping_stats["response_times"][-100:]
        
        ping_stats["total_pings"] = ping_stats.get("total_pings", 0) + 1
        ping_stats["last_ping"] = time.time()
        
        db["ping_stats"] = ping_stats
        save_data(db)
        
        return {
            "success": True,
            "time": response_time,
            "message_id": sent_message
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ------------------- Обработка команд -------------------
def process_command(event, text, prefix):
    """Обработка команд"""
    global db
    
    # Увеличиваем счетчики
    db["commands_used"] = db.get("commands_used", 0) + 1
    db["requests_count"] = db.get("requests_count", 0) + 1
    save_data(db)
    
    # Проверка ЧС
    if is_blocked(event.user_id):
        if event.peer_id == event.user_id:
            send_message(event.user_id, "❌ Вы находитесь в черном списке бота.")
        return
    
    # Проверка тех. работ
    if is_maintenance() and event.user_id not in TECH_ADMINS and event.user_id != ADMIN_ID:
        if event.peer_id == event.user_id:
            send_message(event.user_id, "🔧 Бот находится на технических работах.")
        return
    
    # Разбор команды
    command_parts = text.split()
    if not command_parts:
        return
    
    command = command_parts[0].lower().replace(prefix, "")
    args = command_parts[1:] if len(command_parts) > 1 else []
    
    # Определяем куда отправлять ответ
    def reply(message_text):
        if event.peer_id != event.user_id:
            send_chat_message(event.peer_id, message_text)
        else:
            send_message(event.user_id, message_text)
    
    # Логируем команду
    chat_type = "личка" if event.peer_id == event.user_id else "беседа"
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {chat_type} | {event.user_id}: {command}")
    
    # ------------------- Основные команды -------------------
    if command == "help":
        help_text = """🤖 **Доступные команды:**

**Основные:**
`!help` - показать это сообщение
`!ping` - информация о работе бота
`!ping @пользователь` - проверить доступность пользователя
`!stats` - ваша статистика
`!botstats` - статистика бота

**Друзья:**
`!addfriend @пользователь` - добавить в друзья
`!delfriend @пользователь` - удалить из друзей

**Квесты:**
`!getquests <текст>` - отправить текст квеста
`!quests <дата (22.05.26)>` - список квестов за дату

**Система доверия:**
`!trust @пользователь` - добавить в доверенные
`!untrust @пользователь` - удалить из доверенных

**Администрирование (для тех. админов):**
`!reboot` - перезагрузка бота
`!maintenance on/off` - тех. работы
`!deluser @пользователь` - удалить из БД
`!admin <пароль>` - админ-панель

**Для отдела квестов:** `!help1`"""
        reply(help_text)
    
    elif command == "ping":
        if args:
            target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
            if not target_id:
                reply("❌ Укажите пользователя для пинга (ответом на сообщение или @упоминанием)")
                return
            
            reply(f"🏓 Пингую пользователя...")
            
            result = ping_user(target_id)
            
            if result["success"]:
                ping_text = f"""✅ **Результат пинга для {get_user_name(target_id)}:**

• Время ответа: {result['time']:.2f} мс
• Статус: онлайн"""
                reply(ping_text)
            else:
                reply(f"❌ Пинг не удался: {result['error']}")
            return
        
        avg_req, avg_cmd = calculate_averages()
        uptime = format_uptime()
        commands_total = db.get("commands_used", 0)
        requests_total = db.get("requests_count", 0)
        ping_stats = calculate_ping_stats()
        
        ping_text = f"""🏓 **Pong!**

📊 **Статистика:**
• Средняя нагрузка: {avg_req:.1f} запросов/час
• Средняя команд: {avg_cmd:.1f} команд/час
• Время работы: {uptime}
• Всего команд: {commands_total}
• Всего запросов: {requests_total}
• Доверенных: {len(db['trusted_users'])}
• В ЧС: {len(db['blocked_users'])}
• Префикс: {db.get('prefix', PREFIX)}
• Режим ТО: {'✅' if is_maintenance() else '❌'}

📈 **Статистика пинга:**
• Всего пингов: {ping_stats['total']}
• Среднее время: {ping_stats['avg']:.1f} мс"""
        reply(ping_text)
    
    elif command == "stats":
        user_id = event.user_id
        user_name = get_user_name(user_id)
        
        is_trust = "✅" if is_trusted(user_id) else "❌"
        is_bl = "✅" if is_blocked(user_id) else "❌"
        quest_access = db["quest_access"].get(str(user_id), [])
        quest_access_count = "все" if quest_access == "all" else len(quest_access)
        role = get_staff_role(user_id) or "Нет"
        
        stats_text = f"""📊 **Статистика:** {user_name}

• ID: {user_id}
• В доверии: {is_trust}
• В ЧС: {is_bl}
• Доступ к квестам: {quest_access_count}
• Роль: {role}"""
        reply(stats_text)
    
    elif command == "botstats":
        avg_req, avg_cmd = calculate_averages()
        uptime = format_uptime()
        ping_stats = calculate_ping_stats()
        commands_total = db.get("commands_used", 0)
        
        stats_text = f"""🤖 **Статистика бота**

⏱ Время работы: {uptime}
📈 Средняя нагрузка в час:
   • Запросов: {avg_req:.1f}
   • Команд: {avg_cmd:.1f}
👥 Пользователи:
   • Доверенных: {len(db['trusted_users'])}
   • В ЧС: {len(db['blocked_users'])}
   • С доступом: {len(db['quest_access'])}
   • Сотрудников: {len(db['staff_quest'])}
📊 Всего команд: {commands_total}

📡 **Пинг:** {ping_stats['avg']:.1f} мс (всего: {ping_stats['total']})"""
        reply(stats_text)
    
    # ------------------- Управление друзьями -------------------
    elif command == "addfriend":
        if not is_trusted(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя (ответом или @)")
            return
        
        try:
            vk.friends.add(user_id=target_id)
            reply(f"✅ Запрос в друзья отправлен {get_user_name(target_id)}")
        except Exception as e:
            reply(f"❌ Ошибка: {e}")
    
    elif command == "delfriend":
        if not is_trusted(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
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
        if not is_trusted(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id not in db["trusted_users"]:
            db["trusted_users"].append(target_id)
            save_data(db)
            reply(f"✅ {get_user_name(target_id)} добавлен в доверенные")
        else:
            reply(f"ℹ️ Уже в доверенных")
    
    elif command == "untrust":
        if not is_trusted(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id in db["trusted_users"]:
            db["trusted_users"].remove(target_id)
            save_data(db)
            reply(f"✅ {get_user_name(target_id)} удален из доверенных")
        else:
            reply(f"ℹ️ Не в доверенных")
    
    # ------------------- Квестовая система -------------------
    elif command == "getquests":
        if not is_trusted(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        quest_text = " ".join(args)
        if not quest_text:
            reply("❌ Введите текст квеста")
            return
        
        user_name = get_user_name(event.user_id)
        
        today = datetime.datetime.now().strftime("%d.%m.%y")
        if today not in db["quests"]:
            db["quests"][today] = []
        
        quest_entry = {
            "user_id": event.user_id,
            "user_name": user_name,
            "text": quest_text,
            "timestamp": time.time()
        }
        db["quests"][today].append(quest_entry)
        save_data(db)
        
        if event.peer_id != event.user_id:
            send_chat_message(event.peer_id, f"📝 Квест от {user_name}:\n{quest_text}")
        else:
            reply(f"✅ Квест сохранен за {today}")
    
    elif command == "quests":
        if not is_trusted(event.user_id):
            reply("❌ Нет доступа.")
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
            parts = [result[i:i+4000] for i in range(0, len(result), 4000)]
            for part in parts:
                reply(part)
        else:
            reply(result)
    
    # ------------------- Команды отдела квестов (сокращенно) -------------------
    elif command == "help1":
        if not is_quest_staff(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        help_text = """🎯 **Отдел квестов:**

`!giveaccess @пользователь <команда/all>` - выдать доступ
`!removeaccess @пользователь <команда>` - удалить доступ
`!setrole @пользователь <роль>` - назначить роль
`!removerole @пользователь` - снять роль
`!stafflist` - список сотрудников

**Роли:** Куратор отдела, Наставник отдела, Руководитель отдела, Заместитель руководителя отдела"""
        reply(help_text)
    
    elif command == "giveaccess":
        if not is_quest_staff(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        if len(args) < 2:
            reply("❌ Использование: !giveaccess @пользователь <команда/all>")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        command_name = args[-1]
        if command_name not in ["all", "getquests", "quests", "help1", "stafflist"]:
            reply("❌ Неверная команда")
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
        reply(f"✅ Доступ выдан {get_user_name(target_id)}")
    
    elif command == "removeaccess":
        if not is_quest_staff(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        if len(args) < 2:
            reply("❌ Использование: !removeaccess @пользователь <команда>")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        command_name = args[-1]
        user_access = db["quest_access"].get(str(target_id), [])
        
        if user_access == "all":
            if command_name == "all":
                del db["quest_access"][str(target_id)]
            else:
                reply("❌ Сначала удалите полный доступ: !removeaccess @user all")
                return
        elif isinstance(user_access, list) and command_name in user_access:
            user_access.remove(command_name)
            if not user_access:
                del db["quest_access"][str(target_id)]
            else:
                db["quest_access"][str(target_id)] = user_access
        else:
            reply(f"❌ Нет доступа к {command_name}")
            return
        
        save_data(db)
        reply(f"✅ Доступ удален")
    
    elif command == "listaccess":
        if not is_quest_staff(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        access = db["quest_access"].get(str(target_id), [])
        if access == "all":
            text_access = "🎯 Полный доступ"
        elif access:
            text_access = f"🎯 Доступ: {', '.join(access)}"
        else:
            text_access = "🎯 Нет доступа"
        
        reply(text_access)
    
    elif command == "setrole":
        if not is_quest_staff(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        if len(args) < 2:
            reply("❌ Использование: !setrole @пользователь <роль>")
            return
        
        valid_roles = ["Куратор отдела", "Наставник отдела", "Руководитель отдела", 
                       "Заместитель руководителя отдела"]
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        role = " ".join(args[1:])
        if role not in valid_roles:
            reply(f"❌ Роли: {', '.join(valid_roles)}")
            return
        
        if not can_manage_staff(event.user_id, target_id):
            reply("❌ Недостаточно прав")
            return
        
        db["staff_quest"][str(target_id)] = role
        db["quest_access"][str(target_id)] = "all"
        save_data(db)
        
        reply(f"✅ {get_user_name(target_id)} назначен: {role}")
    
    elif command == "removerole":
        if not is_quest_staff(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if not can_manage_staff(event.user_id, target_id):
            reply("❌ Недостаточно прав")
            return
        
        if str(target_id) in db["staff_quest"]:
            del db["staff_quest"][str(target_id)]
            if db["quest_access"].get(str(target_id)) == "all":
                del db["quest_access"][str(target_id)]
            save_data(db)
            reply(f"✅ Роль снята с {get_user_name(target_id)}")
        else:
            reply(f"ℹ️ Нет роли")
    
    elif command == "stafflist":
        if not is_quest_staff(event.user_id):
            reply("❌ Нет доступа.")
            return
        
        if not db["staff_quest"]:
            reply("📭 Нет сотрудников")
            return
        
        roles_order = ["Куратор отдела", "Наставник отдела", "Руководитель отдела", 
                       "Заместитель руководителя отдела"]
        
        result = "👥 **Сотрудники:**\n\n"
        for role in roles_order:
            members = [uid for uid, r in db["staff_quest"].items() if r == role]
            if members:
                result += f"**{role}:**\n"
                for uid in members:
                    name = get_user_name(int(uid))
                    result += f"  • {name}\n"
                result += "\n"
        
        reply(result)
    
    # ------------------- Администрирование -------------------
    elif command == "admin":
        if len(args) < 1:
            reply("❌ Требуется пароль")
            return
        
        password = args[0]
        if password != ADMIN_PASSWORD:
            reply("❌ Неверный пароль")
            return
        
        if event.user_id not in TECH_ADMINS and event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        admin_text = f"""🔧 **Админ-панель**

`!prefix <новый>` - сменить префикс
`!block @user` - добавить в ЧС
`!unblock @user` - убрать из ЧС
`!maintenance on/off` - тех. работы
`!reboot` - перезагрузка
`!deluser @user` - удалить из БД
`!resetstats` - сбросить статистику

Префикс: `{db.get('prefix', PREFIX)}`"""
        reply(admin_text)
    
    elif command == "prefix":
        if event.user_id not in TECH_ADMINS and event.user_id != ADMIN_ID:
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
        reply(f"✅ Префикс: `{new_prefix}`")
    
    elif command == "block":
        if event.user_id not in TECH_ADMINS and event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id not in db["blocked_users"]:
            db["blocked_users"].append(target_id)
            save_data(db)
            reply(f"✅ {get_user_name(target_id)} в ЧС")
        else:
            reply(f"ℹ️ Уже в ЧС")
    
    elif command == "unblock":
        if event.user_id not in TECH_ADMINS and event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id in db["blocked_users"]:
            db["blocked_users"].remove(target_id)
            save_data(db)
            reply(f"✅ {get_user_name(target_id)} из ЧС")
        else:
            reply(f"ℹ️ Не в ЧС")
    
    elif command == "maintenance":
        if event.user_id not in TECH_ADMINS and event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        if len(args) < 1:
            reply("❌ maintenance on/off")
            return
        
        mode = args[0].lower()
        if mode == "on":
            db["maintenance"] = True
            save_data(db)
            reply("🔧 Тех. работы ВКЛЮЧЕНЫ")
        elif mode == "off":
            db["maintenance"] = False
            save_data(db)
            reply("✅ Тех. работы ВЫКЛЮЧЕНЫ")
        else:
            reply("❌ on или off")
    
    elif command == "reboot":
        if event.user_id not in TECH_ADMINS and event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        reply("🔄 Перезагрузка...")
        save_data(db)
        sys.exit(0)
    
    elif command == "deluser":
        if event.user_id not in TECH_ADMINS and event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        target_id = find_user_id_from_text(text, event.peer_id, event.reply_message)
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id in db["trusted_users"]:
            db["trusted_users"].remove(target_id)
        if target_id in db["blocked_users"]:
            db["blocked_users"].remove(target_id)
        if str(target_id) in db["quest_access"]:
            del db["quest_access"][str(target_id)]
        if str(target_id) in db["staff_quest"]:
            del db["staff_quest"][str(target_id)]
        
        save_data(db)
        reply(f"✅ {get_user_name(target_id)} удален из БД")
    
    elif command == "resetstats":
        if event.user_id not in TECH_ADMINS and event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        db["commands_used"] = 0
        db["requests_count"] = 0
        db["bot_start_time"] = time.time()
        db["ping_stats"] = {
            "total_pings": 0,
            "response_times": []
        }
        save_data(db)
        reply("✅ Статистика сброшена")

# ------------------- Основной цикл -------------------
def main():
    print("=" * 50)
    print("🤖 Страничник запущен на Bothost!")
    print(f"📌 Префикс: {db.get('prefix', PREFIX)}")
    print(f"👤 Ваш ID: {ADMIN_ID}")
    print("💬 Работает в ЛС и беседах")
    print("=" * 50)
    print("Ожидание команд...")
    print()
    
    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW:
                    # Проверяем, что сообщение адресовано нам (в ЛС) или в беседе
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
                                
                                if event.peer_id != event.user_id:
                                    send_chat_message(event.peer_id, f"❌ Ошибка: {str(e)[:100]}")
                                else:
                                    send_message(event.user_id, f"❌ Ошибка: {str(e)[:100]}")
        
        except Exception as e:
            print(f"Ошибка в основном цикле: {e}")
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    main()