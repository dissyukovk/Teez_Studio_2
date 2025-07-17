# telegram_bot/bot_instance.py

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio.client import Redis

from django.conf import settings
from . import config

# --- FSM Хранилище ---
# Используем Redis для хранения состояний диалогов (FSM).
redis_client = Redis(
    host=settings.Q_CLUSTER['redis']['host'],
    port=settings.Q_CLUSTER['redis']['port'],
    db=2,
    decode_responses=True
)
storage = RedisStorage(redis=redis_client)

# --- Настройки по умолчанию для бота ---
default_properties = DefaultBotProperties(
    parse_mode=ParseMode.HTML
)

# --- Инициализация Бота и Диспетчера ---
# Создаем экземпляр бота
bot = Bot(token=config.TELEGRAM_TOKEN, default=default_properties)

# Создаем диспетчер. Он будет обрабатывать все входящие обновления.
dp = Dispatcher(storage=storage)

# ВСЁ! Больше здесь ничего не нужно.
# Строки с `from . import handlers` и `dp.include_router` удалены.
