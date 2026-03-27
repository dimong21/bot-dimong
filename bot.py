import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
import time
import datetime
import json
import os
import re
import sys

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

TECH_ADMINS = {ADMIN_ID}

print("=" * 50)
print("🤖 Страничник запускается...")
print(f"📌 Префикс: {PREFIX}")
print(f"👤 Ваш ID: {ADMIN_ID}")
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
        "trusted_users": [],
        "blocked_users": [],
        "prefix": PREFIX,
        "quests": {},
        "maintenance": False,
        "bot_start_time": time.time(),
        "commands_used": 0
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

# ------------------- Функции -------------------
def send_message(user_id, message):
    try:
        vk.messages.send(user_id=user_id, message=message, random_id=get_random_id())
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def send_chat_message(peer_id, message):
    try:
        vk.messages.send(peer_id=peer_id, message=message, random_id=get_random_id())
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def is_blocked(user_id):
    return user_id in db["blocked_users"]

def get_user_name(user_id):
    try:
        user = vk.users.get(user_ids=user_id)
        if user:
            return f"{user[0]['first_name']} {user[0]['last_name']}"
    except:
        pass
    return f"ID{user_id}"

def format_uptime():
    uptime_seconds = time.time() - db.get("bot_start_time", time.time())
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    return f"{hours} ч, {minutes} мин"

def find_user_id_from_text(text):
    """Поиск ID пользователя в тексте"""
    # Поиск упоминания [id123|text]
    mention_match = re.search(r'\[id(\d+)\|', text)
    if mention_match:
        return int(mention_match.group(1))
    
    # Поиск прямой ссылки
    id_match = re.search(r'id(\d+)', text)
    if id_match:
        return int(id_match.group(1))
    
    return None

def get_reply_user_id(event):
    """Получение ID пользователя из ответа на сообщение"""
    try:
        # Пытаемся получить ID через reply_message
        if hasattr(event, 'reply_message') and event.reply_message:
            return event.reply_message.get('from_id')
        
        # Альтернативный способ через получение сообщения
        if hasattr(event, 'message') and event.message:
            # В VK API reply_message может быть в event.message
            if hasattr(event.message, 'reply_message'):
                return event.message.reply_message.get('from_id')
    except:
        pass
    return None

# ------------------- Обработка команд -------------------
def process_command(event, text, prefix):
    global db
    
    db["commands_used"] = db.get("commands_used", 0) + 1
    save_data(db)
    
    if is_blocked(event.user_id):
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
    
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Команда: {command}")
    
    # ------------------- Основные команды -------------------
    if command == "help":
        reply("""🤖 **Команды:**

`!help` - помощь
`!ping` - статистика
`!stats` - ваша статистика
`!addfriend @пользователь` - добавить в друзья
`!delfriend @пользователь` - удалить из друзей
`!getquests <текст>` - сохранить квест
`!quests <дата>` - квесты за дату
`!trust @user` - добавить в доверенные
`!untrust @user` - удалить из доверенных
`!admin <пароль>` - админ-панель""")
    
    elif command == "ping":
        uptime = format_uptime()
        commands_total = db.get("commands_used", 0)
        
        reply(f"""🏓 **Pong!**

📊 **Статистика:**
• Время работы: {uptime}
• Всего команд: {commands_total}
• Доверенных: {len(db['trusted_users'])}
• В ЧС: {len(db['blocked_users'])}
• Префикс: {db.get('prefix', PREFIX)}""")
    
    elif command == "stats":
        user_name = get_user_name(event.user_id)
        is_trust = "✅" if event.user_id in db["trusted_users"] or event.user_id == ADMIN_ID else "❌"
        reply(f"📊 {user_name}\nID: {event.user_id}\nВ доверии: {is_trust}")
    
    # ------------------- Друзья -------------------
    elif command == "addfriend":
        # Ищем ID в тексте
        target_id = find_user_id_from_text(text)
        
        # Если не нашли, пробуем получить из ответа на сообщение
        if not target_id:
            try:
                # Получаем последние сообщения для поиска реплая
                messages = vk.messages.getHistory(peer_id=event.peer_id, count=1)
                if messages.get('items'):
                    last_msg = messages['items'][0]
                    if last_msg.get('reply_message'):
                        target_id = last_msg['reply_message']['from_id']
            except:
                pass
        
        if not target_id:
            reply("❌ Укажите пользователя (@упоминание или ответом на сообщение)")
            return
        
        try:
            vk.friends.add(user_id=target_id)
            reply(f"✅ Запрос в друзья отправлен {get_user_name(target_id)}")
        except Exception as e:
            reply(f"❌ Ошибка: {e}")
    
    elif command == "delfriend":
        target_id = find_user_id_from_text(text)
        
        if not target_id:
            try:
                messages = vk.messages.getHistory(peer_id=event.peer_id, count=1)
                if messages.get('items'):
                    last_msg = messages['items'][0]
                    if last_msg.get('reply_message'):
                        target_id = last_msg['reply_message']['from_id']
            except:
                pass
        
        if not target_id:
            reply("❌ Укажите пользователя (@упоминание или ответом на сообщение)")
            return
        
        try:
            vk.friends.delete(user_id=target_id)
            reply(f"✅ {get_user_name(target_id)} удален из друзей")
        except Exception as e:
            reply(f"❌ Ошибка: {e}")
    
    # ------------------- Система доверия -------------------
    elif command == "trust":
        if event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        target_id = find_user_id_from_text(text)
        
        if not target_id:
            try:
                messages = vk.messages.getHistory(peer_id=event.peer_id, count=1)
                if messages.get('items'):
                    last_msg = messages['items'][0]
                    if last_msg.get('reply_message'):
                        target_id = last_msg['reply_message']['from_id']
            except:
                pass
        
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
        if event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        target_id = find_user_id_from_text(text)
        
        if not target_id:
            try:
                messages = vk.messages.getHistory(peer_id=event.peer_id, count=1)
                if messages.get('items'):
                    last_msg = messages['items'][0]
                    if last_msg.get('reply_message'):
                        target_id = last_msg['reply_message']['from_id']
            except:
                pass
        
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id in db["trusted_users"]:
            db["trusted_users"].remove(target_id)
            save_data(db)
            reply(f"✅ {get_user_name(target_id)} удален из доверенных")
        else:
            reply(f"ℹ️ Не в доверенных")
    
    # ------------------- Квесты -------------------
    elif command == "getquests":
        quest_text = " ".join(args)
        if not quest_text:
            reply("❌ Введите текст квеста: !getquests <текст>")
            return
        
        today = datetime.datetime.now().strftime("%d.%m.%y")
        if today not in db["quests"]:
            db["quests"][today] = []
        
        db["quests"][today].append({
            "user_id": event.user_id,
            "user_name": get_user_name(event.user_id),
            "text": quest_text
        })
        save_data(db)
        
        # Отправляем в чат
        if event.peer_id != event.user_id:
            send_chat_message(event.peer_id, f"📝 Квест от {get_user_name(event.user_id)}:\n{quest_text}")
        else:
            reply(f"✅ Квест сохранен за {today}")
    
    elif command == "quests":
        date = args[0] if args else ""
        if not date:
            reply("❌ Укажите дату в формате ДД.ММ.ГГ (например, 22.05.26)")
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
    
    # ------------------- Администрирование -------------------
    elif command == "admin":
        if len(args) < 1:
            reply("❌ Требуется пароль: !admin <пароль>")
            return
        
        if args[0] != ADMIN_PASSWORD:
            reply("❌ Неверный пароль")
            return
        
        if event.user_id != ADMIN_ID:
            reply("❌ Нет прав администратора")
            return
        
        reply(f"""🔧 **Админ-панель**

`!prefix <новый>` - сменить префикс
`!block @user` - добавить в ЧС
`!unblock @user` - убрать из ЧС
`!reboot` - перезагрузка

Текущий префикс: `{db.get('prefix', PREFIX)}`""")
    
    elif command == "prefix":
        if event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        if len(args) < 1:
            reply("❌ Укажите новый префикс")
            return
        
        new_prefix = args[0]
        if len(new_prefix) > 5:
            reply("❌ Префикс слишком длинный (макс 5 символов)")
            return
        
        db["prefix"] = new_prefix
        save_data(db)
        reply(f"✅ Префикс изменен на `{new_prefix}`")
    
    elif command == "block":
        if event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        target_id = find_user_id_from_text(text)
        
        if not target_id:
            try:
                messages = vk.messages.getHistory(peer_id=event.peer_id, count=1)
                if messages.get('items'):
                    last_msg = messages['items'][0]
                    if last_msg.get('reply_message'):
                        target_id = last_msg['reply_message']['from_id']
            except:
                pass
        
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id not in db["blocked_users"]:
            db["blocked_users"].append(target_id)
            save_data(db)
            reply(f"✅ {get_user_name(target_id)} добавлен в ЧС")
        else:
            reply(f"ℹ️ Уже в ЧС")
    
    elif command == "unblock":
        if event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        target_id = find_user_id_from_text(text)
        
        if not target_id:
            try:
                messages = vk.messages.getHistory(peer_id=event.peer_id, count=1)
                if messages.get('items'):
                    last_msg = messages['items'][0]
                    if last_msg.get('reply_message'):
                        target_id = last_msg['reply_message']['from_id']
            except:
                pass
        
        if not target_id:
            reply("❌ Укажите пользователя")
            return
        
        if target_id in db["blocked_users"]:
            db["blocked_users"].remove(target_id)
            save_data(db)
            reply(f"✅ {get_user_name(target_id)} удален из ЧС")
        else:
            reply(f"ℹ️ Не в ЧС")
    
    elif command == "reboot":
        if event.user_id != ADMIN_ID:
            reply("❌ Нет прав")
            return
        
        reply("🔄 Перезагрузка бота...")
        save_data(db)
        sys.exit(0)

# ------------------- Основной цикл -------------------
def main():
    print("=" * 50)
    print("🤖 Бот-страничник запущен!")
    print(f"📌 Префикс: {db.get('prefix', PREFIX)}")
    print("💬 Работает в ЛС и беседах")
    print("=" * 50)
    print("Ожидание команд...")
    
    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW:
                    # Проверяем что сообщение адресовано нам (в ЛС) или в беседе
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
                                import traceback
                                traceback.print_exc()
        except Exception as e:
            print(f"Ошибка в основном цикле: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
