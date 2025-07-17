# okz/tasks.py
import asyncio
from django.utils import timezone
from django.db import transaction
from django_q.tasks import async_task
from asgiref.sync import async_to_sync
# Импортируем модели из вашего приложения core
from core.models import Order, OrderProduct, OrderStatus
from auto.models import RGTScripts
# Импортируем нашу "отправлялку" сообщений из приложения бота

#Сообщение об очередях
def schedule_queue_stats_okz():
    """
    Задача для django-q, которая собирает статистику по очередям ОКЗ
    напрямую из базы данных и отправляет ее в Telegram.
    """
    print("Запуск задачи schedule_queue_stats_okz из приложения okz...")

    # --- Логика Django ORM ---
    created_orders = Order.objects.filter(status__id=2)
    created_orders_count = created_orders.count()
    created_orders_products_count = OrderProduct.objects.filter(order__in=created_orders).count()

    assembly_orders = Order.objects.filter(status__id=3)
    assembly_orders_count = assembly_orders.count()
    assembly_orders_products_count = OrderProduct.objects.filter(order__in=assembly_orders).count()

    # Вспомогательная функция для склонений
    def prepositional_form(count, singular, plural):
        if not isinstance(count, int): return plural
        return singular if (count % 10 == 1 and count % 100 != 11) else plural

    # Формируем текст сообщения
    message_text = (
        "Текущая очередь на ФС:\n\n"
        f"📩 Созданные заказы (сбор еще не начат) - {created_orders_products_count} SKU в {created_orders_count} {prepositional_form(created_orders_count, 'заказе', 'заказах')}\n"
        f"📦 Собранные заказы (сбор начат, но еще не приняты на ФС) - {assembly_orders_products_count} SKU в {assembly_orders_count} {prepositional_form(assembly_orders_count, 'заказе', 'заказах')}"
    )

    # ID чата и темы для отправки
    target_chat_id = "-1002453118841"
    target_thread_id = 9

    # Используем нашу асинхронную функцию для отправки
    print(f"Попытка отправки статистики ОКЗ в чат {target_chat_id}...")
    async_task(
        'telegram_bot.tasks.send_message_task',  # <-- Вызываем БЕЗОПАСНУЮ СИНХРОННУЮ ОБЕРТКУ
        chat_id=target_chat_id,
        text=message_text,
        message_thread_id=target_thread_id
    )
    print("Задача schedule_queue_stats_okz завершена.")

#Сброс заказов и сообщение
def schedule_order_status_refresh():
    """
    Задача для сброса статуса "зависших" в сборке заказов.
    """
    print("Запуск задачи schedule_order_status_refresh...")

    try:
        # Загружаем настройки, как вы и описали
        rgt_settings = RGTScripts.load()
    except Exception as e:
        print(f"Критическая ошибка: Не удалось загрузить настройки RGTScripts. Задача прервана. Ошибка: {e}")
        return # Прерываем выполнение

    # 1. Проверяем, включен ли скрипт
    if not rgt_settings.OKZReorderEnable:
        print("Сброс заказов отключен в настройках (OKZReorderEnable=False). Задача завершена.")
        return

    # 2. Проверяем, задан ли порог времени
    threshold_duration = rgt_settings.OKZReorderTreshold
    if not threshold_duration:
        print("Ошибка конфигурации: Сброс заказов включен, но порог времени (OKZReorderTreshold) не установлен. Задача прервана.")
        return

    # 3. Вычисляем пороговую дату и получаем статусы
    threshold_date = timezone.now() - threshold_duration
    try:
        status_to_check = OrderStatus.objects.get(id=3) # "На сборке"
        status_to_set = OrderStatus.objects.get(id=2)   # "Создан"
    except OrderStatus.DoesNotExist as e:
        print(f"Критическая ошибка: Не найден статус заказа (id=2 или id=3). Задача прервана. Ошибка: {e}")
        return

    # 4. Находим и обновляем заказы в рамках одной транзакции для надежности
    updated_orders_info = []
    with transaction.atomic():
        # Находим заказы, которые "зависли"
        orders_to_update = Order.objects.filter(
            status=status_to_check,
            assembly_date__lt=threshold_date
        ).select_for_update() # Блокируем строки для безопасного обновления

        if not orders_to_update:
            print("Не найдено заказов для сброса статуса. Задача завершена.")
            return

        # Сохраняем информацию для уведомления
        for order in orders_to_update:
            updated_orders_info.append(str(order.OrderNumber))

        # Массово обновляем заказы
        count = orders_to_update.update(status=status_to_set, assembly_date=None)
        print(f"Статус был сброшен для {count} заказов.")

    # 5. Если были обновленные заказы, отправляем уведомление в Telegram
    if updated_orders_info:
        orders_str = ", ".join(updated_orders_info)
        message_text = (
            f"Заказы {orders_str} находились в Сборе долгое время.\n\n"
            "Статусы этих заказов были сброшены, они появятся как новые."
        )

        # ID чата и темы для отправки
        target_chat_id = "-1002453118841"
        target_thread_id = 9

        print(f"Попытка отправки уведомления о сбросе статусов в чат {target_chat_id}...")
        async_task(
            'telegram_bot.tasks.send_message_task',  # <-- Вызываем БЕЗОПАСНУЮ СИНХРОННУЮ ОБЕРТКУ
            chat_id=target_chat_id,
            text=message_text,
            message_thread_id=target_thread_id
        )

    print("Задача schedule_order_status_refresh завершена.")
