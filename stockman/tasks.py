# stockman/tasks.py

from collections import defaultdict
from django.utils import timezone
from aiogram.utils.markdown import hbold
from asgiref.sync import async_to_sync
from django_q.tasks import async_task
from core.models import ProductOperation

def schedule_product_operations_stats():
    """
    Задача для сбора и отправки статистики по операциям товароведов.
    """
    print("Запуск задачи schedule_product_operations_stats...")

    # 1. Определяем временные рамки
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 2. Получаем все нужные операции за месяц одним запросом
    operations = ProductOperation.objects.filter(
        date__range=(start_of_month, now),
        operation_type__id__in=[3, 4]  # 3 - Принято, 4 - Отправлено
    ).select_related('user') # Подтягиваем связанного пользователя

    # 3. Обрабатываем данные в Python, чтобы не делать лишних запросов к БД
    today_stats = defaultdict(lambda: {'Принято': 0, 'Отправлено': 0, 'Итого': 0})
    month_stats = defaultdict(lambda: {'Принято': 0, 'Отправлено': 0, 'Итого': 0})

    for op in operations:
        if not op.user:
            continue # Пропускаем операции без пользователя

        # Формируем имя пользователя
        username = f"{op.user.first_name} {op.user.last_name}".strip()
        if not username:
            username = op.user.username

        # Определяем тип операции и обновляем статистику за месяц
        op_type_str = ''
        if op.operation_type_id == 3:
            op_type_str = 'Принято'
        elif op.operation_type_id == 4:
            op_type_str = 'Отправлено'

        month_stats[username][op_type_str] += 1
        month_stats[username]['Итого'] += 1

        # Если операция была сегодня, обновляем статистику за сегодня
        if op.date.date() == now.date():
            today_stats[username][op_type_str] += 1
            today_stats[username]['Итого'] += 1

    # 4. Формируем сообщение с использованием HTML-разметки
    message_lines = [hbold("📊 СТАТИСТИКА ПО ТОВАРОВЕДАМ!")]

    message_lines.append("\n" + hbold("📅 Сегодня:"))
    if today_stats:
        # Сортируем по Итого за сегодня
        sorted_today = sorted(today_stats.items(), key=lambda item: item[1]['Итого'], reverse=True)
        for user, stats in sorted_today:
            message_lines.append(f"{hbold(user)}:")
            message_lines.append(f"  📥 Принято - {stats['Принято']}")
            message_lines.append(f"  📤 Отправлено - {stats['Отправлено']}")
            message_lines.append(f"  🧮 Итого - {stats['Итого']}")
    else:
        message_lines.append("Нет данных за сегодня")

    message_lines.append("\n" + hbold("🗓 С начала месяца:"))
    if month_stats:
        # Сортируем по Итого за месяц
        sorted_month = sorted(month_stats.items(), key=lambda item: item[1]['Итого'], reverse=True)
        for user, stats in sorted_month:
            message_lines.append(f"{hbold(user)}:")
            message_lines.append(f"  📥 Принято - {stats['Принято']}")
            message_lines.append(f"  📤 Отправлено - {stats['Отправлено']}")
            message_lines.append(f"  🧮 Итого - {stats['Итого']}")
    else:
        message_lines.append("Нет данных за период")

    message_text = "\n".join(message_lines)

    # 5. Отправляем сообщение в заданный чат
    target_chat_id = "-1002213405207" # Используем строку для надежности

    print(f"Попытка отправки статистики товароведов в чат {target_chat_id}...")
    async_task(
        'telegram_bot.tasks.send_message_task', # Путь к нашей функции
        chat_id=target_chat_id,
        text=message_text
    )
    print("Задача schedule_product_operations_stats завершена.")
