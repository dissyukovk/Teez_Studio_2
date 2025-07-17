from django.core.management.base import BaseCommand
from core.tasks import export_daily_stats  # Импорт задачи

class Command(BaseCommand):
    help = 'Экспорт статистики в Google Таблицу'

    def handle(self, *args, **kwargs):
        self.stdout.write("Начинается экспорт статистики...")
        try:
            export_daily_stats()  # Запуск вашей функции
            self.stdout.write(self.style.SUCCESS("Экспорт завершён успешно!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка при экспорте: {e}"))
