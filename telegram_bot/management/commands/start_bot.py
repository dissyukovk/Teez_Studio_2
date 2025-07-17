# telegram_bot/management/commands/start_bot.py
import asyncio
from django.core.management.base import BaseCommand
from telegram_bot.bot_instance import bot, dp # Импортируем и диспетчер dp

class Command(BaseCommand):
    help = 'Запускает Telegram бота в режиме опроса (polling)'

    async def handle_async(self):
        """Асинхронный основной метод для запуска бота."""
        # Удаляем веб-хук перед запуском, чтобы избежать конфликтов
        await bot.delete_webhook(drop_pending_updates=True)

        self.stdout.write(self.style.SUCCESS('Запуск бота...'))

        # Запускаем получение обновлений
        await dp.start_polling(bot)

    def handle(self, *args, **options):
        """Синхронный wrapper для вызова асинхронного кода."""
        try:
            asyncio.run(self.handle_async())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Работа бота прервана.'))
