# telegram_bot/management/commands/setup_bot.py
import asyncio # <<< Добавляем импорт
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram_bot.bot_instance import bot
from telegram_bot.config import TELEGRAM_TOKEN

class Command(BaseCommand):
    help = 'Установка и удаление веб-хука для Telegram бота'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true', help='Удалить веб-хук')
        parser.add_argument('--url', type=str, help='Публичный URL для веб-хука')

    # vvv Переименовываем handle в handle_async vvv
    async def handle_async(self, *args, **options):
        if options['delete']:
            await bot.delete_webhook()
            self.stdout.write(self.style.SUCCESS('Веб-хук успешно удален.'))
            return

        if not options['url']:
            self.stdout.write(self.style.ERROR('Необходимо указать --url.'))
            return

        webhook_url = f"{options['url']}/bot/webhook/"
        await bot.set_webhook(webhook_url)
        self.stdout.write(self.style.SUCCESS(f'Веб-хук успешно установлен на {webhook_url}'))

    # vvv Создаем синхронный handle, который вызывает асинхронный vvv
    def handle(self, *args, **options):
        asyncio.run(self.handle_async(*args, **options))
