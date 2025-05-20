import asyncio
from join_telegram_chats import account_manager, save_all_chats_to_db
from telethon import TelegramClient

async def main():
    acc = account_manager.accounts[account_manager.current_account_index]
    client = TelegramClient(acc.session_name, acc.api_id, acc.api_hash)
    await client.start(phone=acc.phone)
    await save_all_chats_to_db(client)
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main()) 