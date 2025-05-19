import os
import asyncio
import re
import random
import time
from datetime import datetime
import sqlite3
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatAdminRequiredError, UsernameInvalidError, UsernameNotOccupiedError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import GetDialogsRequest, GetHistoryRequest, AddReactionRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import InputPeerEmpty, InputMessageID, ReactionEmoji
from delay_manager import DelayManager
from account_manager import AccountManager

# Учетные данные
API_ID = 20723031
API_HASH = '05f59ebab48ab890899a8aa5b4b8626d'
PHONE = '+17656617177'

ERROR_LOG_FILE = 'errors.log'
DB_FILE = 'chats.db'

# Создаем экземпляры менеджеров
delay_manager = DelayManager(base_delay=30, max_extra=10)
account_manager = AccountManager()

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
    - https://t.me/joinchat/XXXX
    - https://t.me/+XXXX
    """
    link = link.strip()
    # Проверка на инвайт-ссылку
    invite_match = re.search(r'(?:t\.me/(joinchat/|\+)|telegram\.me/(joinchat/|\+))([\w-]+)', link)
    if invite_match:
        return {'type': 'invite', 'hash': invite_match.group(3)}
    # Если это просто имя пользователя без @, добавляем @
    if not any(char in link for char in ['/', '@', 'http']):
        link = '@' + link
    # Удаляем @ если он есть
    if link.startswith('@'):
        link = link[1:]
    # Обработка URL
    if 'http' in link or 't.me' in link or 'telegram.me' in link:
        match = re.search(r'(?:t\.me|telegram\.me)/([^/]+)', link)
        if match:
            link = match.group(1)
    return {'type': 'username', 'username': link}

# --- Проверка наличия чата в базе ---
def is_chat_in_db(chatname):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Проверяем по username (основной способ)
    c.execute('SELECT 1 FROM chats WHERE username = ?', (chatname,))
    result = c.fetchone()
    conn.close()
    return result is not None

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

# --- Эмуляция активности пользователя ---
async def emulate_human_activity(client):
    """
    Эмулирует действия обычного пользователя: просмотр чатов, чтение сообщений, реакции.
    """
    try:
        # Получаем список чатов
        dialogs = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=50,
            hash=0
        ))
        chats = [d for d in dialogs.chats if hasattr(d, 'id')]
        if not chats:
            return
        # Выбираем случайный чат
        chat = random.choice(chats)
        print(f"🤖 Эмуляция активности: просмотр чата {getattr(chat, 'title', chat.id)}")
        # Получаем историю сообщений
        history = await client(GetHistoryRequest(
            peer=chat,
            offset_id=0,
            offset_date=None,
            add_offset=0,
            limit=50,
            max_id=0,
            min_id=0,
            hash=0
        ))
        messages = [m for m in history.messages if hasattr(m, 'id')]
        if messages:
            # Читаем 3 случайных сообщения
            for msg in random.sample(messages, min(3, len(messages))):
                print(f"  👁️ Чтение сообщения {msg.id}")
                # Пробуем поставить реакцию (лайк)
                try:
                    await client(AddReactionRequest(
                        peer=chat,
                        id=[msg.id],
                        reaction=[ReactionEmoji(emoticon='👍')],
                        big=True
                    ))
                    print(f"  👍 Поставлена реакция на сообщение {msg.id}")
                except Exception:
                    pass
    except Exception as e:
        print(f"⚠️ Ошибка эмуляции активности: {e}")

# --- Вступление в чаты с проверкой ---
async def join_chat(client, chat_link, account):
    try:
        normalized = normalize_chat_link(chat_link)
        if normalized['type'] == 'invite':
            chat_id = normalized['hash']
            if is_chat_in_db(chat_id):
                print(f"⏩ Уже состоите в чате (инвайт): {chat_id}, пропускаю...")
                account_manager.mark_join(account, chat_id, success=False, error_message="Already joined (invite)")
                return True
            print(f"Попытка присоединиться по инвайт-ссылке: {chat_id}")
            await client(ImportChatInviteRequest(chat_id))
            print(f"✅ Успешно присоединился по инвайт-ссылке: {chat_id}")
            account_manager.mark_join(account, chat_id, success=True)
            await delay_manager.adaptive_sleep()
            # Иногда эмулируем активность
            if random.random() < 0.2:
                await emulate_human_activity(client)
            return True
        else:
            chatname = normalized['username']
            if is_chat_in_db(chatname):
                print(f"⏩ Уже состоите в чате: {chatname}, пропускаю...")
                account_manager.mark_join(account, chatname, success=False, error_message="Already joined")
                return True
            print(f"Попытка присоединиться к чату: {chatname}")
            await client(JoinChannelRequest(chatname))
            print(f"✅ Успешно присоединился к чату: {chatname}")
            account_manager.mark_join(account, chatname, success=True)
            await delay_manager.adaptive_sleep()
            # Иногда эмулируем активность
            if random.random() < 0.2:
                await emulate_human_activity(client)
            return True
    except FloodWaitError as e:
        wait_time = e.seconds
        print(f"⚠️ FloodWait! Ожидание {wait_time} секунд...")
        log_error(chat_link, f"FloodWait: ожидание {wait_time} секунд", str(e))
        account_manager.mark_join(account, chat_link, success=False, error_message=f"FloodWait: {wait_time}s")
        account_manager.mark_account_flood_wait(account, wait_time)
        # После FloodWait обязательно эмулируем активность
        await emulate_human_activity(client)
        return False
    except ChatAdminRequiredError as e:
        print(f"❌ Не удалось присоединиться к чату {chat_link}: требуется одобрение администратора")
        log_error(chat_link, "Требуется одобрение администратора", str(e))
        account_manager.mark_join(account, chat_link, success=False, error_message="Admin approval required")
        return True
    except UsernameInvalidError as e:
        print(f"❌ Неверный формат имени пользователя: {chat_link}")
        log_error(chat_link, "Неверный формат имени пользователя", str(e))
        account_manager.mark_join(account, chat_link, success=False, error_message="Invalid username")
        return True
    except UsernameNotOccupiedError as e:
        print(f"❌ Чат не существует: {chat_link}")
        log_error(chat_link, "Чат не существует", str(e))
        account_manager.mark_join(account, chat_link, success=False, error_message="Chat doesn't exist")
        return True
    except Exception as e:
        print(f"❌ Ошибка при присоединении к чату {chat_link}: {str(e)}")
        log_error(chat_link, "Другая ошибка", str(e))
        account_manager.mark_join(account, chat_link, success=False, error_message=str(e))
        await delay_manager.adaptive_sleep()
        return True

async def print_account_stats(account):
    """Выводит статистику по аккаунту"""
    stats = account_manager.get_account_stats(account)
    print(f"\n📊 Статистика аккаунта {account.phone}:")
    print(f"  • Всего успешных вступлений: {stats['total_successful']}")
    print(f"  • Вступлений за последние 24 часа: {stats['last_24h']}")
    print(f"  • Вступлений за последний час: {stats['last_hour']}")

# --- Основной сценарий ---
async def main():
    init_db()
    # Загружаем список чатов из файла
    with open('chat_list.txt', 'r', encoding='utf-8') as f:
        chat_links = [line.strip() for line in f if line.strip()]

    while chat_links:  # Продолжаем, пока есть чаты для вступления
        # Создание клиента
        client = await account_manager.create_client()
        if not client:
            print("❌ Не удалось создать клиент. Проверьте файл accounts.json")
            # Делаем длительную паузу перед следующей попыткой
            print("⏳ Ожидание 5 минут перед следующей попыткой...")
            await asyncio.sleep(300)
            continue

        try:
            print("🔌 Подключение к Telegram...")
            await print_chat_limits(client)
            await save_all_chats_to_db(client)
            
            # Получаем текущий аккаунт
            current_account = account_manager.accounts[account_manager.current_account_index]
            
            # Выводим статистику аккаунта
            await print_account_stats(current_account)
            
            # Обрабатываем чаты для текущего аккаунта
            while chat_links and not account_manager.should_switch_account():
                chat_link = chat_links[0]
                success = await join_chat(client, chat_link, current_account)
                if success:
                    chat_links.pop(0)  # Удаляем обработанный чат из списка
                else:
                    # Если не удалось вступить из-за FloodWait, переключаемся на другой аккаунт
                    break
            
            # Если остались чаты, переключаемся на следующий аккаунт
            if chat_links:
                print("🔄 Переключение на следующий аккаунт...")
                await client.disconnect()
                # Делаем случайную паузу перед переключением
                switch_delay = random.uniform(30, 60)
                print(f"⏳ Пауза {switch_delay:.1f} секунд перед переключением аккаунта...")
                await asyncio.sleep(switch_delay)
            
        except Exception as e:
            print(f"❌ Произошла ошибка: {str(e)}")
            await client.disconnect()
            # Делаем паузу перед следующей попыткой
            await asyncio.sleep(random.uniform(60, 120))
        finally:
            await client.disconnect()
            print("👋 Отключение от Telegram")

    print("✅ Все чаты обработаны!")

if __name__ == '__main__':
    asyncio.run(main()) 