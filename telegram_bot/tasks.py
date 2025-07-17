# telegram_bot/tasks.py
import asyncio
import logging

from aiogram.exceptions import TelegramAPIError


logger = logging.getLogger(__name__)

# НЕ импортируем 'bot' на уровне модуля
# from .bot_instance import bot  <--- УДАЛИТЬ ЭТУ СТРОКУ

async def _send_and_close(bot_instance, chat_id, text, send_kwargs):
    """
    Асинхронная "внутренняя" функция, которая отправляет сообщение
    и корректно закрывает сессию бота после этого.
    """
    try:
        # send_kwargs может содержать parse_mode, reply_to_message_id и др.
        await bot_instance.send_message(chat_id=chat_id, text=text, **send_kwargs)
        logger.info(f"Сообщение успешно отправлено в чат {chat_id}")
    except TelegramAPIError as e:
        logger.error(f"Ошибка API при отправке сообщения в чат {chat_id}: {e}")
    finally:
        if getattr(bot_instance, 'session', None):
            await bot_instance.session.close()

def send_message_task(chat_id: int, text: str, message_thread_id: int | None = None, **kwargs):
    """
    Синхронная задача для django-q.
    Она принимает любые kwargs (parse_mode, disable_web_page_preview и т.д.)
    и передаёт их далее в _send_and_close.
    """
    from .bot_instance import bot
    # собираем параметры, которые отправим в send_message
    send_kwargs = {}
    if message_thread_id is not None:
        send_kwargs['message_thread_id'] = message_thread_id
    # kwargs может содержать parse_mode, reply_markup и любые другие
    send_kwargs.update(kwargs)

    try:
        asyncio.run(_send_and_close(bot, chat_id, text, send_kwargs))
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при выполнении send_message_task для чата {chat_id}: {e}")
