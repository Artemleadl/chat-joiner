import asyncio
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from account_manager import AccountManager

async def main():
    # Создаем менеджер аккаунтов
    account_manager = AccountManager()
    
    # Получаем второй аккаунт
    second_account = account_manager.accounts[1]  # Индекс 1 для второго аккаунта
    
    print(f"🔌 Подключение к Telegram для аккаунта {second_account.phone}...")
    
    # Создаем клиент
    client = TelegramClient(second_account.session_name, second_account.api_id, second_account.api_hash)
    
    try:
        # Подключаемся и авторизуемся
        await client.start(phone=second_account.phone)
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