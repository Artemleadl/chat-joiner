import os
import asyncio
import re
import random
from datetime import datetime
import sqlite3
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatAdminRequiredError, UsernameInvalidError, UsernameNotOccupiedError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty

# Учетные данные
API_ID = 20723031
API_HASH = '05f59ebab48ab890899a8aa5b4b8626d'
PHONE = '+17656617177'

ERROR_LOG_FILE = 'errors.log'
DB_FILE = 'chats.db'

# --- Работа с базой данных ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY,
            title TEXT,
            username TEXT,
            chat_type TEXT,
            date_added TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_chat_to_db(chat_id, title, username, chat_type):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO chats (id, title, username, chat_type, date_added)
        VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, title, username, chat_type, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

# --- Логирование ошибок ---
def log_error(chat, reason, details=None):
    with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{now}] Чат: {chat} | Причина: {reason}\n")
        if details:
            f.write(f"    Детали: {details}\n")

# --- Нормализация и задержки ---
def normalize_chat_link(link):
    """
    Нормализует различные форматы ссылок на чаты Telegram
    Поддерживаемые форматы:
    - https://t.me/chatname
    - t.me/chatname
    - @chatname
    - chatname
    - https://telegram.me/chatname
    - telegram.me/chatname
    """
    # Удаляем все пробелы
    link = link.strip()
    
    # Если это просто имя пользователя без @, добавляем @
    if not any(char in link for char in ['/', '@', 'http']):
        link = '@' + link
    
    # Удаляем @ если он есть
    if link.startswith('@'):
        link = link[1:]
    
    # Обработка URL
    if 'http' in link or 't.me' in link or 'telegram.me' in link:
        # Извлекаем имя пользователя из URL
        match = re.search(r'(?:t\.me|telegram\.me)/([^/]+)', link)
        if match:
            link = match.group(1)
    
    return link

# --- Проверка наличия чата в базе ---
def is_chat_in_db(chatname):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Проверяем по username (основной способ)
    c.execute('SELECT 1 FROM chats WHERE username = ?', (chatname,))
    result = c.fetchone()
    conn.close()
    return result is not None

# --- Адаптивная задержка (30-40 секунд) ---
async def adaptive_sleep(base=30, max_extra=10):
    delay = base + random.uniform(0, max_extra)
    print(f"⏳ Ожидание {delay:.1f} секунд перед следующим чатом...")
    await asyncio.sleep(delay)

# --- Сохранение чатов аккаунта в базу ---
async def save_all_chats_to_db(client):
    print("📥 Сохраняю данные о чатах аккаунта в базу данных...")
    chats = []
    last_date = None
    chunk_size = 200
    has_more = True
    offset_id = 0
    while has_more:
        result = await client(GetDialogsRequest(
            offset_date=last_date,
            offset_id=offset_id,
            offset_peer=InputPeerEmpty(),
            limit=chunk_size,
            hash=0
        ))
        chats.extend(result.chats)
        if not result.chats or len(result.chats) < chunk_size:
            has_more = False
        else:
            offset_id = result.chats[-1].id
    for chat in chats:
        title = getattr(chat, 'title', None)
        username = getattr(chat, 'username', None)
        chat_type = type(chat).__name__
        save_chat_to_db(chat.id, title, username, chat_type)
    print(f"✅ В базу сохранено {len(chats)} чатов/каналов/групп.")

# --- Вывод лимитов ---
async def print_chat_limits(client):
    # Получаем список всех чатов, каналов и групп
    chats = []
    last_date = None
    chunk_size = 200
    has_more = True
    offset_id = 0
    while has_more:
        result = await client(GetDialogsRequest(
            offset_date=last_date,
            offset_id=offset_id,
            offset_peer=InputPeerEmpty(),
            limit=chunk_size,
            hash=0
        ))
        chats.extend(result.chats)
        if not result.chats or len(result.chats) < chunk_size:
            has_more = False
        else:
            offset_id = result.chats[-1].id
    print(f"\nℹ️ Ваш аккаунт состоит в {len(chats)} чатах/каналах/группах.")
    print("Лимиты Telegram:")
    print("  • Обычный аккаунт: до 500 чатов/групп/каналов")
    print("  • Премиум-аккаунт: до 1000 чатов/групп/каналов\n")

# --- Вступление в чаты с проверкой ---
async def join_chat(client, chat_link, flood_delay=0):
    try:
        normalized_link = normalize_chat_link(chat_link)
        # Проверяем, состоит ли уже аккаунт в этом чате
        if is_chat_in_db(normalized_link):
            print(f"⏩ Уже состоите в чате: {normalized_link}, пропускаю...")
            return
        print(f"Попытка присоединиться к чату: {normalized_link}")
        await client(JoinChannelRequest(normalized_link))
        print(f"✅ Успешно присоединился к чату: {normalized_link}")
        await adaptive_sleep()
    except FloodWaitError as e:
        wait_time = e.seconds + flood_delay
        print(f"⚠️ FloodWait! Ожидание {wait_time} секунд...")
        log_error(normalized_link, f"FloodWait: ожидание {wait_time} секунд", str(e))
        await asyncio.sleep(wait_time)
        await join_chat(client, chat_link, flood_delay + 5)
    except ChatAdminRequiredError as e:
        print(f"❌ Не удалось присоединиться к чату {normalized_link}: требуется одобрение администратора")
        log_error(normalized_link, "Требуется одобрение администратора", str(e))
    except UsernameInvalidError as e:
        print(f"❌ Неверный формат имени пользователя: {normalized_link}")
        log_error(normalized_link, "Неверный формат имени пользователя", str(e))
    except UsernameNotOccupiedError as e:
        print(f"❌ Чат не существует: {normalized_link}")
        log_error(normalized_link, "Чат не существует", str(e))
    except Exception as e:
        print(f"❌ Ошибка при присоединении к чату {normalized_link}: {str(e)}")
        log_error(normalized_link, "Другая ошибка", str(e))
        await adaptive_sleep()

# --- Основной сценарий ---
async def main():
    init_db()
    # Список ссылок на чаты для присоединения
    chat_links = [
        "@zhukova_soza",
        "@boldiching",
        "@bypanica",
        "@cogachat",
        "@Fenomenlichnosti",
        "@gadeckymarafon",
        "@luck_will",
        "@misliletopischat"
    ]

    # Создание клиента
    client = TelegramClient('session_name', API_ID, API_HASH)
    
    try:
        print("🔌 Подключение к Telegram...")
        await client.start(phone=PHONE)
        print("✅ Успешное подключение к Telegram")
        await print_chat_limits(client)
        await save_all_chats_to_db(client)
        for chat_link in chat_links:
            await join_chat(client, chat_link)
        # Повторно выводим статистику после всех попыток вступления
        await print_chat_limits(client)
        # Повторно обновляем базу данных после вступления
        await save_all_chats_to_db(client)
    except Exception as e:
        print(f"❌ Произошла ошибка: {str(e)}")
    finally:
        await client.disconnect()
        print("👋 Отключение от Telegram")

if __name__ == '__main__':
    asyncio.run(main()) 