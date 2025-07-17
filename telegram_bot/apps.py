# telegram_bot/apps.py
from django.apps import AppConfig

class TelegramBotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'telegram_bot'

    # vvv ДОБАВЬТЕ ЭТОТ МЕТОД vvv
    def ready(self):
        """
        Этот метод вызывается, когда Django полностью готов к работе.
        Это идеальное место для импорта и регистрации наших обработчиков.
        """
        print("Django is ready. Registering bot handlers...")
        # Импортируем диспетчер и обработчики здесь, внутри ready()
        from .bot_instance import dp
        from . import handlers

        # Подключаем роутер из handlers.py к главному диспетчеру
        dp.include_router(handlers.router)
        print("Bot handlers registered.")
