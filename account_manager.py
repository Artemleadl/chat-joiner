from dataclasses import dataclass
from typing import List, Optional, Dict
import asyncio
from telethon import TelegramClient
from telethon.errors import FloodWaitError
import json
import os
import random
import time
import sqlite3
from datetime import datetime, timedelta

@dataclass
class TelegramAccount:
    phone: str
    api_id: int
    api_hash: str
    session_name: str
    min_join_interval: int = 60
    max_joins_per_hour: int = 20
    max_joins_per_day: int = 100
    device_model: str = "PC"
    system_version: str = "Windows 10"
    app_version: str = "4.8"
    lang_code: str = "en"
    last_used: float = 0
    flood_wait_until: float = 0
    cooldown_until: float = 0
    joins_today: int = 0
    last_join_time: float = None
    total_joins: int = 0
    last_reset_time: float = None

class AccountManager:
    def __init__(self, accounts_file: str = 'accounts.json', db_file: str = 'joins_history.db'):
        self.accounts_file = accounts_file
        self.db_file = db_file
        self.accounts: List[TelegramAccount] = []
        self.current_account_index = 0
        self.init_db()
        self.load_accounts()
        self.joins_before_switch = random.randint(10, 20)  # Увеличено с 5-15 до 10-20
        self.current_joins = 0

    def init_db(self):
        """Инициализирует базу данных для хранения истории вступлений"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS joins_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_phone TEXT,
                chat_name TEXT,
                timestamp REAL,
                success BOOLEAN,
                error_message TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def load_accounts(self):
        """Загружает аккаунты из JSON файла"""
        if os.path.exists(self.accounts_file):
            with open(self.accounts_file, 'r') as f:
                accounts_data = json.load(f)
                self.accounts = [TelegramAccount(**acc) for acc in accounts_data]
        else:
            example_accounts = [
                {
                    "phone": "+1234567890",
                    "api_id": 12345,
                    "api_hash": "your_api_hash_here",
                    "session_name": "account1",
                    "min_join_interval": 30,
                    "max_joins_per_hour": 50,
                    "max_joins_per_day": 200
                }
            ]
            with open(self.accounts_file, 'w') as f:
                json.dump(example_accounts, f, indent=4)
            print(f"Создан файл {self.accounts_file} с примером структуры. Пожалуйста, заполните его своими данными.")

    def save_accounts(self):
        """Сохраняет аккаунты в JSON файл"""
        accounts_data = [
            {
                "phone": acc.phone,
                "api_id": acc.api_id,
                "api_hash": acc.api_hash,
                "session_name": acc.session_name,
                "min_join_interval": acc.min_join_interval,
                "max_joins_per_hour": acc.max_joins_per_hour,
                "max_joins_per_day": acc.max_joins_per_day
            }
            for acc in self.accounts
        ]
        with open(self.accounts_file, 'w') as f:
            json.dump(accounts_data, f, indent=4)

    def get_joins_count(self, account: TelegramAccount, time_window: int) -> int:
        """Получает количество вступлений за указанный период времени в секундах"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        current_time = time.time()
        start_time = current_time - time_window
        
        c.execute('''
            SELECT COUNT(*) FROM joins_history 
            WHERE account_phone = ? AND timestamp > ? AND success = 1
        ''', (account.phone, start_time))
        
        count = c.fetchone()[0]
        conn.close()
        return count

    def can_join_now(self, account: TelegramAccount) -> bool:
        """Проверяет, может ли аккаунт сейчас вступить в чат"""
        current_time = time.time()
        
        # Проверяем cooldown
        if current_time < account.cooldown_until:
            return False

        # Проверяем количество вступлений за последний час
        joins_last_hour = self.get_joins_count(account, 3600)
        if joins_last_hour >= account.max_joins_per_hour:
            # Устанавливаем cooldown до следующего часа
            account.cooldown_until = current_time + 3600 + random.uniform(60, 300)
            return False

        # Проверяем количество вступлений за последние 24 часа
        joins_last_day = self.get_joins_count(account, 86400)
        if joins_last_day >= account.max_joins_per_day:
            # Устанавливаем cooldown до следующего дня
            account.cooldown_until = current_time + 86400 + random.uniform(300, 900)
            return False

        # Проверяем минимальный интервал между вступлениями
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('''
            SELECT timestamp FROM joins_history 
            WHERE account_phone = ? AND success = 1 
            ORDER BY timestamp DESC LIMIT 1
        ''', (account.phone,))
        
        last_join = c.fetchone()
        conn.close()
        
        if last_join and current_time - last_join[0] < account.min_join_interval:
            return False

        return True

    def get_next_available_account(self) -> Optional[TelegramAccount]:
        """Получает следующий доступный аккаунт"""
        if not self.accounts:
            return None

        # Проверяем все аккаунты, начиная с текущего
        for _ in range(len(self.accounts)):
            account = self.accounts[self.current_account_index]
            if account.flood_wait_until <= time.time() and self.can_join_now(account):
                return account
            self.current_account_index = (self.current_account_index + 1) % len(self.accounts)

        return None

    async def create_client(self) -> Optional[TelegramClient]:
        """Создает клиент Telegram для следующего доступного аккаунта"""
        account = self.get_next_available_account()
        if not account:
            print("❌ Нет доступных аккаунтов")
            return None

        client = TelegramClient(account.session_name, account.api_id, account.api_hash)
        try:
            await client.start(phone=account.phone)
            # Устанавливаем параметры устройства в сессии
            session = client.session
            session.device_model = getattr(account, 'device_model', 'PC')
            session.system_version = getattr(account, 'system_version', 'Windows 10')
            session.app_version = getattr(account, 'app_version', '4.8')
            session.lang_code = getattr(account, 'lang_code', 'en')
            await client.session.save()
            account.last_used = time.time()
            return client
        except Exception as e:
            print(f"❌ Ошибка при создании клиента для аккаунта {account.phone}: {str(e)}")
            return None

    def should_switch_account(self) -> bool:
        """Проверяет, нужно ли переключить аккаунт"""
        self.current_joins += 1
        if self.current_joins >= self.joins_before_switch:
            self.current_joins = 0
            self.joins_before_switch = random.randint(10, 20)
            return True
        return False

    def mark_join(self, account: TelegramAccount, chat_name: str, success: bool = True, error_message: str = None):
        """Отмечает вступление в чат в базе данных"""
        current_time = time.time()
        
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('''
            INSERT INTO joins_history (account_phone, chat_name, timestamp, success, error_message)
            VALUES (?, ?, ?, ?, ?)
        ''', (account.phone, chat_name, current_time, success, error_message))
        conn.commit()
        conn.close()

        if success:
            # Устанавливаем cooldown на случайный интервал
            account.cooldown_until = current_time + random.uniform(
                account.min_join_interval,
                account.min_join_interval * 1.5
            )

    def mark_account_flood_wait(self, account: TelegramAccount, wait_time: int):
        """Отмечает аккаунт как ожидающий FloodWait"""
        account.flood_wait_until = time.time() + wait_time
        self.current_account_index = (self.current_account_index + 1) % len(self.accounts)
        self.save_accounts()

    def get_account_stats(self, account: TelegramAccount) -> Dict:
        """Получает статистику по аккаунту"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        # Общее количество успешных вступлений
        c.execute('''
            SELECT COUNT(*) FROM joins_history 
            WHERE account_phone = ? AND success = 1
        ''', (account.phone,))
        total_successful = c.fetchone()[0]
        
        # Количество вступлений за последние 24 часа
        c.execute('''
            SELECT COUNT(*) FROM joins_history 
            WHERE account_phone = ? AND success = 1 AND timestamp > ?
        ''', (account.phone, time.time() - 86400))
        last_24h = c.fetchone()[0]
        
        # Количество вступлений за последний час
        c.execute('''
            SELECT COUNT(*) FROM joins_history 
            WHERE account_phone = ? AND success = 1 AND timestamp > ?
        ''', (account.phone, time.time() - 3600))
        last_hour = c.fetchone()[0]
        
        conn.close()
        
        return {
            "total_successful": total_successful,
            "last_24h": last_24h,
            "last_hour": last_hour
        } 