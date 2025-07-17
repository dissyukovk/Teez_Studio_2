# dynamic_stats_sender.py
import requests
from datetime import datetime, date
from telebot import TeleBot
import logging
from .botconfig import BACKEND_URL, TELEGRAM_TOKEN
from .photographers import fetch_priority_strequests_data, format_priority_strequests_message

# Инициализируем экземпляр бота
bot = TeleBot(TELEGRAM_TOKEN)

#статистика по фотографам
def send_photographers_dynamic_stats():
    """
    Получает статистику с начала текущего месяца по сегодняшний день с эндпоинта photographers_statistic,
    форматирует сообщение и отправляет его в выбранный чат на основе вычисления разницы дней от базовой даты.
    """
    # Определяем сегодняшнюю дату и начало месяца
    today = datetime.now().date()
    first_day_of_month = today.replace(day=1)
    # Форматируем даты в формате дд.мм.гггг
    start_date_str = first_day_of_month.strftime('%d.%m.%Y')
    today_str = today.strftime('%d.%m.%Y')
    
    # Запрашиваем данные по эндпоинту
    endpoint_url = f"{BACKEND_URL}/mn/photographers_statistic/"
    params = {
        "date_from": start_date_str,
        "date_to": today_str,
    }
    
    try:
        response = requests.get(endpoint_url, params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Ошибка при запросе статистики: {e}")
        return
    
    # Извлекаем статистику за сегодня и общий итог
    today_stats = data.get(today_str, {})
    total_stats = data.get("Total", {})
    
    # Формируем текст сообщения
    message_lines = []
    message_lines.append("Снято за сегодня:")
    if today_stats:
        # Сортируем по убыванию количества
        for photographer, count in sorted(today_stats.items(), key=lambda x: x[1], reverse=True):
            message_lines.append(f"{photographer} - {count}")
    else:
        message_lines.append("Нет данных за сегодня")
    
    message_lines.append("\nИтого с начала месяца:")
    if total_stats:
        # Сортируем по убыванию количества
        for photographer, count in sorted(total_stats.items(), key=lambda x: x[1], reverse=True):
            message_lines.append(f"{photographer} - {count}")
    else:
        message_lines.append("Нет данных за периода")
    
    message_text = "\n".join(message_lines)
    
    # Вычисляем разницу дней между сегодняшним днём и базовой датой 11.03.2025
    base_date = datetime.strptime("10.03.2025", "%d.%m.%Y").date()
    days_diff = (today - base_date).days
    mod = days_diff % 4
    remainder_fraction = mod / 4.0
    
    # Определяем чат для отправки сообщения
    if remainder_fraction in [0.0, 0.25]:
        target_chat = "-1002397911962"
    elif remainder_fraction in [0.5, 0.75]:
        target_chat = "-1002347741124"
    else:
        target_chat = "1788046722"  # запасной вариант
    
    # Отправляем сообщение
    try:
        bot.send_message(target_chat, message_text, parse_mode="Markdown")
        print(f"Сообщение отправлено в чат {target_chat}")
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")

def get_queue_stats_message():
    """
    Получает данные с эндпоинта очередей и формирует сообщение.
    Возвращает сформированное сообщение или None в случае ошибки.
    """
    # Убедитесь, что URL указывает на ваш эндпоинт get_current_queues
    api_url = f"{BACKEND_URL}/mn/queues/" # Полный URL эндпоинта
    try:
        response = requests.get(api_url)
        response.raise_for_status() # Проверка на ошибки HTTP (4xx, 5xx)
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе очередей ({api_url}): {e}")
        return None
    except Exception as e:
        # Обработка других возможных ошибок, например, JSONDecodeError
        print(f"Неожиданная ошибка при обработке ответа от {api_url}: {e}")
        return None

    # --- Извлечение данных из ответа ---
    created = data.get("created_orders", {})
    assembly = data.get("assembly_orders", {})
    shooting = data.get("shooting_requests", {})
    retouch = data.get("retouch_queue", {})
    photo_check = data.get("photo_check_queue", {})
    retouch_check = data.get("retouch_check_queue", {})
    render_q = data.get("render_queue", {})
    render_upload = data.get("render_upload_queue", {})
    fs_upload = data.get("fs_photo_upload_queue", {})
    # ---> Извлекаем данные для новой очереди
    real_shooting = data.get("real_shooting_queue", {})

    # Получаем счетчики, используя .get с дефолтным значением 0
    created_orders_count = created.get("orders_count", 0)
    created_products_count = created.get("products_count", 0)

    assembly_orders_count = assembly.get("orders_count", 0)
    assembly_products_count = assembly.get("products_count", 0)

    shooting_requests_count = shooting.get("requests_count", 0)
    shooting_products_count = shooting.get("products_count", 0)

    retouch_count = retouch.get("count", 0)

    photo_check_requests_count = photo_check.get("requests_count", 0)
    photo_check_products_count = photo_check.get("products_count", 0)

    retouch_check_requests_count = retouch_check.get("requests_count", 0)
    retouch_check_products_count = retouch_check.get("products_count", 0)

    render_queue_count = render_q.get("count", 0)
    render_upload_queue_count = render_upload.get("count", 0)
    fs_photo_upload_queue_count = fs_upload.get("count", 0)
    # ---> Получаем счетчик для новой очереди
    real_shooting_count = real_shooting.get("count", 0)


    # --- Вспомогательная функция для склонений ---
    def prepositional_form(count, singular, plural):
        """
        Для чисел, оканчивающихся на 1 (но не 11) используем форму singular,
        для остальных – форму plural.
        """
        # Добавим проверку на None или нечисловые значения
        if not isinstance(count, (int, float)):
            return plural # Возвращаем множественное число по умолчанию
        # Основная логика склонения
        if count % 10 == 1 and count % 100 != 11:
            return singular
        else:
            return plural

    # --- Формирование итогового сообщения ---
    # Добавлена строка для "Реальная очередь на съемку"
    # Можно выбрать другой эмодзи, если 🔁 не подходит (например, 📸 или 🔄)
    message = (
        "Текущие очереди:\n\n"
        f"📩 *Созданные заказы:* {created_products_count} SKU в {created_orders_count} {prepositional_form(created_orders_count, 'заказе', 'заказах')}\n\n"
        f"📦 *На сборке:* {assembly_products_count} SKU в {assembly_orders_count} {prepositional_form(assembly_orders_count, 'заказе', 'заказах')}\n\n"
        f"📸 *Очередь на съемку на фс:* {shooting_products_count} SKU в {shooting_requests_count} {prepositional_form(shooting_requests_count, 'заявке', 'заявках')}\n\n"
        f"🤔 *Очередь на проверку фото:* {photo_check_products_count} SKU в {photo_check_requests_count} {prepositional_form(photo_check_requests_count, 'заявке', 'заявках')}\n\n"
        f"🖌 *Очередь на ретушь:* {retouch_count} SKU\n\n"
        f"👀 *Очередь на проверку ретуши:* {retouch_check_products_count} SKU в {retouch_check_requests_count} {prepositional_form(retouch_check_requests_count, 'заявке', 'заявках')}\n\n"
        f"🖼 *Очередь на рендер:* {render_queue_count} SKU\n\n"
        f"📤 *Очередь на загрузку фото от ФС:* {fs_photo_upload_queue_count} SKU\n\n"
        f"⬆️ *Очередь на загрузку рендеров:* {render_upload_queue_count} SKU\n\n"
        f"📸 *Реальная очередь на съемку отклоненных:* {real_shooting_count} SKU"
    )
    return message

def send_queue_stats(chat_id, topic=None):
    """
    Отправляет сообщение со статистикой очередей в указанный чат.
    Используется для ответа на запрос /queue.
    
    Если параметр topic задан, сообщение отправляется в соответствующую тему (message_thread_id).
    """
    message = get_queue_stats_message()
    if message is None:
        return
    try:
        if topic is not None:
            bot.send_message(chat_id, message, message_thread_id=topic)
        else:
            bot.send_message(chat_id, message)
    except Exception as e:
        print(f"Ошибка отправки сообщения в чат {chat_id} с топиком {topic}: {e}")

def send_queue_stats_scheduled():
    """
    Отправляет сообщение со статистикой очередей в два предопределённых чата.
    Используется для отправки по расписанию.
    """
    # Задайте реальные chat_id
    chat_ids = [-1002559221974]
    message = get_queue_stats_message()
    if message is None:
        return
    for chat_id in chat_ids:
        try:
            bot.send_message(chat_id, message)
        except Exception as e:
            print(f"Ошибка отправки сообщения в чат {chat_id}: {e}")

#сообщение по очередям для окз
def get_queue_stats_okz_message():
    """
    Получает данные с эндпоинта очередей и формирует сообщение.
    Возвращает сформированное сообщение или None в случае ошибки.
    """
    try:
        response = requests.get(f"{BACKEND_URL}/mn/queues/")
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Ошибка при запросе очередей: {e}")
        return None

    # Извлекаем данные
    created = data.get("created_orders", {})
    assembly = data.get("assembly_orders", {})
    shooting = data.get("shooting_requests", {})
    retouch = data.get("retouch_queue", {})

    created_orders_count = created.get("orders_count", 0)
    created_products_count = created.get("products_count", 0)

    assembly_orders_count = assembly.get("orders_count", 0)
    assembly_products_count = assembly.get("products_count", 0)

    shooting_requests_count = shooting.get("requests_count", 0)
    shooting_products_count = shooting.get("products_count", 0)

    retouch_count = retouch.get("count", 0)

    # Функция для выбора правильной формы существительного в предлоге "в"
    def prepositional_form(count, singular, plural):
        """
        Для чисел, оканчивающихся на 1 (но не 11) используем форму singular,
        для остальных – форму plural.
        """
        return singular if (count % 10 == 1 and count % 100 != 11) else plural

    # Формируем сообщение с эмодзи и правильными склонениями:
    message = (
        "Текущая очередь на ФС:\n\n"
        f"📩 Созданные заказы (сбор еще не начат) - {created_products_count} SKU в {created_orders_count} {prepositional_form(created_orders_count, 'заказе', 'заказах')}\n"
        f"📦 Собранные заказы (сбор начат, но еще не приняты на ФС) - {assembly_products_count} SKU в {assembly_orders_count} {prepositional_form(assembly_orders_count, 'заказе', 'заказах')}\n"
    )
    return message

def send_queue_stats_okz_scheduled():
    """
    Отправляет сообщение со статистикой очередей в два предопределённых чата с жестко заданными топиками:
    - Для чата -100123123123 используется топик 123
    - Для чата -100456456456 используется топик 456
    """
    message = get_queue_stats_okz_message()
    if message is None:
        return

    # Жестко заданные пары (chat_id, topic)
    chats = [
        (-1002453118841, 9)
    ]
    
    for chat_id, topic in chats:
        try:
            bot.send_message(chat_id, message, message_thread_id=topic)
        except Exception as e:
            print(f"Ошибка отправки сообщения в чат {chat_id} с топиком {topic}: {e}")

#Сброс статусов заказов и отправка сообщения
def scheduled_order_status_refresh():
    """
    Метод для телеграм-бота, который обращается к эндпоинту order-status-refresh,
    проверяет наличие обновлённых заказов и, если они есть, отправляет сообщение в заданный чат и тред.
    """
    url = f"{BACKEND_URL}/auto/order-status-refresh/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        # Логирование ошибки (можно заменить на ваш способ логирования)
        print(f"Ошибка при запросе к {url}: {e}")
        return

    updated_orders = data.get("updated_orders")
    if updated_orders:
        # Извлекаем номера заказов
        order_numbers = [
            str(order.get("OrderNumber"))
            for order in updated_orders
            if order.get("OrderNumber") is not None
        ]
        if order_numbers:
            orders_str = ", ".join(order_numbers)
            message_text = (
                f"Заказы {orders_str} находились в Сборе долгое время.\n\n"
                "Статусы этих заказов были сброшены, они появятся как новые."
            )
            bot.send_message(
                chat_id=-1002453118841,
                text=message_text,
                message_thread_id=9
            )
    # scheduled

#Отправка статистики по товароведам - для периодической отправки
def send_product_operations_stats():
    """
    Получает статистику по товароведам с начала текущего месяца до сегодняшнего дня,
    формирует сообщение и отправляет его в чат -1002213405207.

    Структура сообщения:
    
    📊 *Статистика по товароведам!*
    
    📅 *Сегодня:*
    👤 *Иван Иванов*:
      📥 Принято - <значение>
      📤 Отправлено - <значение>
      🧮 Итого - <значение>
    👤 *Петр Петров*:
      📥 Принято - <значение>
      📤 Отправлено - <значение>
      🧮 Итого - <значение>
    
    🗓 *С начала месяца:*
    👤 *Иван Иванов*:
      📥 Принято - <значение>
      📤 Отправлено - <значение>
      🧮 Итого - <значение>
    и т.д.
    """
    from datetime import datetime

    today = datetime.now().date()
    first_day = today.replace(day=1)
    start_date_str = first_day.strftime('%d.%m.%Y')
    today_str = today.strftime('%d.%m.%Y')
    
    endpoint_url = f"{BACKEND_URL}/mn/product-operations-stats/"
    params = {
        "date_from": start_date_str,
        "date_to": today_str,
    }
    
    try:
        response = requests.get(endpoint_url, params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Ошибка при запросе статистики по товароведам: {e}")
        return

    # Извлекаем статистику за сегодняшний день и за весь период (ключ "Итого")
    today_stats = data.get(today_str, {})
    month_stats = data.get("Итого", {})

    message_lines = []
    message_lines.append("📊 *СТАТИСТИКА!*")
    message_lines.append("")
    
    # Статистика за сегодня
    message_lines.append("📅 *Сегодня:*")
    message_lines.append("")
    if today_stats:
        for user, stats in today_stats.items():
            accepted = stats.get("Принято", 0)
            sent = stats.get("Отправлено", 0)
            total = stats.get("Итого", 0)
            message_lines.append(f"*{user}*:")
            message_lines.append(f"  📥 Принято - {accepted}")
            message_lines.append(f"  📤 Отправлено - {sent}")
            message_lines.append(f"  🧮 Итого - {total}")
    else:
        message_lines.append("Нет данных за сегодня")
    
    message_lines.append("")
    
    # Статистика с начала месяца
    message_lines.append("🗓 *С начала месяца:*")
    message_lines.append("")
    if month_stats:
        for user, stats in month_stats.items():
            accepted = stats.get("Принято", 0)
            sent = stats.get("Отправлено", 0)
            total = stats.get("Итого", 0)
            message_lines.append(f"*{user}*:")
            message_lines.append(f"  📥 Принято - {accepted}")
            message_lines.append(f"  📤 Отправлено - {sent}")
            message_lines.append(f"  🧮 Итого - {total}")
    else:
        message_lines.append("Нет данных за периода")
    
    message_text = "\n".join(message_lines)
    
    target_chat = "-1002213405207"
    
    try:
        bot.send_message(target_chat, message_text, parse_mode="Markdown")
        print(f"Сообщение статистики по товароведам отправлено в чат {target_chat}")
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")

#отправка статистики по загрузкам в телеграм чат
def get_daily_moderation_stats_message():
    """
    Получает статистику модерации за СЕГОДНЯ с эндпоинта Django
    и формирует сообщение.

    Возвращает:
        tuple: Кортеж (str: Форматированное сообщение или сообщение об отсутствии данных, int: ID чата)
               В случае ошибки при запросе или обработке данных возвращает (None, None).
    """
    # ID чата теперь определен внутри функции
    TARGET_CHAT_ID = -1002513626060

    try:
        # 1. Получаем сегодняшнюю дату
        today_date_obj = date.today()
        # Форматируем дату в нужный формат dd.mm.yyyy
        today_date_str = today_date_obj.strftime("%d.%m.%Y")

        # 2. Формируем URL для API запроса
        api_url = f"{BACKEND_URL}/rd/senior_moderation_stats/{today_date_str}/{today_date_str}/"
        # print(f"Запрос статистики по URL: {api_url}") # Опционально для отладки

        # 3. Выполняем GET запрос к API
        response = requests.get(api_url, timeout=15) # Таймаут запроса
        response.raise_for_status() # Проверяем на ошибки HTTP (4xx, 5xx)

        # 4. Парсим JSON ответ
        data = response.json()
        print(f"Получены данные: {data}") # Опционально для отладки

        # 5. Извлекаем статистику за сегодня
        if today_date_str not in data:
            print(f"В ответе API нет данных за {today_date_str}.") # Можно оставить print для отладки
            # Возвращаем сообщение об отсутствии данных и ID чата
            return (f"Нет данных по модерации за {today_date_str}.", TARGET_CHAT_ID)

        moderator_stats = data[today_date_str]

        if not moderator_stats: # Проверяем, есть ли вообще данные по модераторам за этот день
             print(f"Данные по модераторам за {today_date_str} отсутствуют.") # Можно оставить print для отладки
             # Возвращаем сообщение об отсутствии загрузок и ID чата
             return (f"За сегодня ({today_date_str}) еще не было загрузок.", TARGET_CHAT_ID)

        # 6. Формируем сообщение
        message_lines = ["Загружено за сегодня:"]
        # Сортируем модераторов по имени для упорядоченного вывода
        sorted_moderators = sorted(moderator_stats.items())

        for moderator_name, stats in sorted_moderators:
            # Используем .get с 0 по умолчанию
            uploaded_count = stats.get('Uploaded', 0)
            message_lines.append(f"{moderator_name} - {uploaded_count}")

        # Возвращаем готовое сообщение и ID чата
        message_text = "\n".join(message_lines)

    

    except requests.exceptions.Timeout:
        print(f"Ошибка: Запрос к {api_url} превысил таймаут.") # Оставляем print для диагностики
        return (None, None) # Возвращаем None, None при ошибке
    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при запросе статистики модерации: {e}")
        return (None, None)
    except ValueError as e: # Ошибка декодирования JSON
        print(f"Ошибка обработки ответа API (не JSON?): {e}")
        return (None, None)
    except Exception as e:
        # Ловим любые другие непредвиденные ошибки
        print(f"Непредвиденная ошибка при получении статистики модерации: {e}")
        return (None, None)

    if message_text:
        try:
            # Используем объект 'bot', который должен быть доступен
            # Используем ID чата, определенный в начале функции
            # Используем parse_mode="Markdown", как вы указали
            bot.send_message(TARGET_CHAT_ID, message_text, parse_mode="Markdown")
            print(f"Сообщение статистики отправлено в чат {TARGET_CHAT_ID}")
        except Exception as e:
            # Ловим любую ошибку при отправке
            print(f"Ошибка при отправке сообщения в чат {TARGET_CHAT_ID}: {e}")
    else:
        # Этот блок выполнится, если message_text остался None
        # (что не должно произойти при текущей логике, но для полноты)
        print("Не удалось сформировать текст сообщения для отправки.")

# ФУНКЦИЯ для отправки ежедневного списка приоритетных заявок
def send_daily_priority_strequests_notification():
    """
    Получает, форматирует и отправляет список приоритетных заявок на съемку.
    Вызывается по расписанию.
    """
    # ID чата для отправки, указанный в запросе
    TARGET_CHAT_ID = -1002371513464 

    logging.info("Запрос данных для ежедневного уведомления о приоритетных заявках...")
    strequests_data = fetch_priority_strequests_data() # Функция из photographers.py
    
    if strequests_data is None:
        logging.error("Не удалось получить данные о приоритетных заявках. Уведомление не будет отправлено.")
        # Можно добавить отправку уведомления об ошибке администратору, если это критично
        # bot.send_message(ADMIN_CHAT_ID, "Ошибка получения данных для приоритетных заявок ST.")
        return

    message_to_send = format_priority_strequests_message(strequests_data) # Функция из photographers.py

    if message_to_send:
        try:
            bot.send_message(TARGET_CHAT_ID, message_to_send)
            logging.info(f"Сообщение о приоритетных заявках успешно отправлено в чат {TARGET_CHAT_ID}")
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения о приоритетных заявках в чат {TARGET_CHAT_ID}: {e}")
    else:
        logging.info("Нет приоритетных заявок для отправки сегодня, или данные были пусты после форматирования.")
