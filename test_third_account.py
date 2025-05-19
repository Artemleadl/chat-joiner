import asyncio
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from account_manager import AccountManager

async def main():
    # Создаем менеджер аккаунтов
    account_manager = AccountManager()
    
    # Получаем третий аккаунт
    third_account = account_manager.accounts[2]  # Индекс 2 для третьего аккаунта
    
    print(f"🔌 Подключение к Telegram для аккаунта {third_account.phone}...")
    
    # Создаем клиент
    client = TelegramClient(third_account.session_name, third_account.api_id, third_account.api_hash)
    
    try:
        # Подключаемся и авторизуемся
        await client.start(phone=third_account.phone)
        print("✅ Успешное подключение к Telegram")
        
        # Пробуем вступить в тестовый чат
        chat_name = "chat_biznes1"
        print(f"Попытка присоединиться к чату: {chat_name}")
        
        try:
            await client(JoinChannelRequest(chat_name))
            print(f"✅ Успешно присоединился к чату: {chat_name}")
        except Exception as e:
            print(f"❌ Ошибка при присоединении к чату: {str(e)}")
            
    except Exception as e:
        print(f"❌ Ошибка при подключении: {str(e)}")
    finally:
        await client.disconnect()
        print("👋 Отключение от Telegram")

if __name__ == '__main__':
    asyncio.run(main()) 