import asyncio
import random
import time
from datetime import datetime


class DelayManager:
    def __init__(self, base_delay=45, max_extra=15):
        self.base_delay = base_delay
        self.max_extra = max_extra
        self.last_action_time = 0
        self.consecutive_joins = 0
        self.last_flood_wait_time = 0

    async def adaptive_sleep(self):
        """
        Делает адаптивную паузу между вступлениями в чаты.
        Пауза увеличивается с каждым последовательным вступлением.
        """
        # Увеличиваем задержку с каждым последовательным вступлением
        current_delay = self.base_delay + (self.consecutive_joins * 5)
        delay = current_delay + random.uniform(0, self.max_extra)
        
        print(f"⏳ Ожидание {delay:.1f} секунд перед следующим чатом...")
        await asyncio.sleep(delay)
        self.last_action_time = time.time()
        self.consecutive_joins += 1

    async def flood_wait(self, wait_time):
        """
        Делает паузу на указанное время (в секундах) при получении FloodWait от Telegram.
        После FloodWait увеличивает базовые задержки.
        """
        print(f"⚠️ FloodWait! Ожидание {wait_time} секунд...")
        await asyncio.sleep(wait_time)
        self.last_action_time = time.time()
        self.last_flood_wait_time = time.time()
        
        # Увеличиваем базовые задержки после FloodWait
        self.base_delay = min(90, self.base_delay + 15)  # Увеличиваем, но не более 90 секунд
        self.max_extra = min(30, self.max_extra + 5)     # Увеличиваем, но не более 30 секунд
        self.consecutive_joins = 0  # Сбрасываем счетчик последовательных вступлений

    def get_time_since_last_action(self):
        """
        Возвращает время (в секундах), прошедшее с момента последнего действия.
        """
        return time.time() - self.last_action_time

    def should_increase_delay(self):
        """
        Проверяет, нужно ли увеличить задержку на основе времени с последнего FloodWait.
        """
        if self.last_flood_wait_time == 0:
            return False
        time_since_flood = time.time() - self.last_flood_wait_time
        return time_since_flood < 3600  # В течение часа после FloodWait 