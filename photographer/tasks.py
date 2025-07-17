# photographer/tasks.py
import logging
import re
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Q, Count, Exists, OuterRef, Min, Value, F
from django.db.models.functions import Coalesce
from aiogram.utils.markdown import hbold, hcode
from asgiref.sync import async_to_sync
from django_q.tasks import async_task

# Импортируем google api клиенты
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Импортируем модели и задачу отправки
from core.models import STRequest, STRequestProduct, STRequestType
from stockman.views import determine_and_set_strequest_type

logger = logging.getLogger(__name__)

def _get_photographer_stats(start_date, end_date):
    products_filter = (
        Q(strequestproduct__photo_status__id__in=[1, 2, 25]) &
        Q(strequestproduct__sphoto_status__id=1)
    )

    stats = (
        STRequest.objects
        .filter(photo_date__range=(start_date, end_date),
                photographer__isnull=False)
        # группируем по фотографу и собираем имя/username
        .values(
            'photographer__first_name',
            'photographer__last_name',
            'photographer__username',
        )
        # сразу считаем все связанные strequestproduct по условию
        .annotate(
            total_products=Count(
                'strequestproduct',
                filter=products_filter,
            )
        )
        .order_by('-total_products')
    )

    result = []
    for item in stats:
        count = item['total_products']
        if count > 0:
            # Собираем отображаемое имя
            name = f"{item['photographer__first_name']} {item['photographer__last_name']}".strip()
            if not name:
                name = item['photographer__username']
            result.append({'name': name, 'count': count})
    return result


def schedule_photographer_stats():
    """
    Основная задача для сбора и отправки статистики по фотографам.
    """
    print("Запуск задачи schedule_photographer_stats...")

    # 1. Определяем временные рамки
    now = timezone.now()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 2. Получаем статистику за сегодня и за месяц
    today_stats = _get_photographer_stats(start_of_today, now)
    month_stats = _get_photographer_stats(start_of_month, now)

    # 3. Формируем сообщение с жирным текстом
    message_lines = [hbold("Снято за сегодня:")]
    if today_stats:
        for stat in today_stats:
            message_lines.append(f"{hbold(stat['name'])} - {stat['count']}")
    else:
        message_lines.append("Нет данных за сегодня")

    message_lines.append("\n" + hbold("Итого с начала месяца:"))
    if month_stats:
        for stat in month_stats:
            message_lines.append(f"{hbold(stat['name'])} - {stat['count']}")
    else:
        message_lines.append("Нет данных за период")

    message_text = "\n".join(message_lines)

    # 4. Вычисляем, в какой чат отправить сообщение
    base_date = datetime.strptime("10.03.2025", "%d.%m.%Y").date()
    days_diff = (now.date() - base_date).days
    remainder_fraction = (days_diff % 4) / 4.0

    if remainder_fraction in [0.0, 0.25]:
        target_chat_id = "-1002397911962"
    elif remainder_fraction in [0.5, 0.75]:
        target_chat_id = "-1002347741124"
    else:
        target_chat_id = "1788046722"  # Запасной вариант

    # 5. Отправляем сообщение
    print(f"Попытка отправки статистики фотографов в чат {target_chat_id}...")
    async_task(
        'telegram_bot.tasks.send_message_task', # Путь к нашей функции
        chat_id=target_chat_id,
        text=message_text
    )
    print("Задача schedule_photographer_stats завершена.")


#Определить тип заявки - одноразовая задача
def update_all_strequest_types():
    """
    Пробегаем по всем STRequest со статусом=2 и STRequestTypeBlocked=False
    и пересчитываем им STRequestType через утилиту.
    """
    qs = STRequest.objects.filter(status_id=2, STRequestTypeBlocked=False)
    for st in qs:
        # determine_and_set_strequest_type сразу сохраняет, если нужно
        determine_and_set_strequest_type(st.RequestNumber)

# --- Сообщение о приоритетных заявках ---
def send_priority_strequests_notification():
    """
    Основная задача: получает, форматирует и отправляет список 
    приоритетных заявок на съемку, сгруппированных по типу.
    Все переменные и хелперы определены внутри.
    """
    # --- Конфигурация задачи ---
    TARGET_CHAT_ID = -1002371513464
    LIMIT_NORMAL = 10
    LIMIT_CLOTHING = 5
    LIMIT_KGT = 3
    TYPE_NORMAL_ID = 1    # 'Обычные товары'
    TYPE_CLOTHING_ID = 2  # 'Одежда' (предположение)
    TYPE_KGT_ID = 3       # 'КГТ' (предположение)

    def _fetch_and_group_priority_requests():
        """Вложенная функция для получения и группировки заявок."""
        logger.info("Получение приоритетных заявок из БД...")
        
        queryset = STRequest.objects.filter(status_id=2)
        
        priority_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            product__priority=True
        )
        queryset = queryset.annotate(has_priority_product=Exists(priority_subquery))
        
        very_far_date = timezone.make_aware(datetime(9999, 12, 31, 23, 59, 59))
        queryset = queryset.annotate(
            min_income_date_raw=Min('strequestproduct__product__income_date')
        ).annotate(
            min_income_date=Coalesce('min_income_date_raw', Value(very_far_date))
        )
        
        queryset = queryset.order_by(
            F('has_priority_product').desc(),
            F('min_income_date').asc()
        ).values('RequestNumber', 'STRequestType_id')
        
        grouped_requests = {"normal": [], "clothing": [], "kgt": []}
        all_requests = list(queryset)

        for req in all_requests:
            req_type = req.get('STRequestType_id')
            req_num = req.get('RequestNumber')

            if req_type == TYPE_NORMAL_ID and len(grouped_requests["normal"]) < LIMIT_NORMAL:
                grouped_requests["normal"].append(req_num)
            elif req_type == TYPE_CLOTHING_ID and len(grouped_requests["clothing"]) < LIMIT_CLOTHING:
                grouped_requests["clothing"].append(req_num)
            elif req_type == TYPE_KGT_ID and len(grouped_requests["kgt"]) < LIMIT_KGT:
                grouped_requests["kgt"].append(req_num)

        logger.info(f"Найдено заявок: Обычные={len(grouped_requests['normal'])}, Одежда={len(grouped_requests['clothing'])}, КГТ={len(grouped_requests['kgt'])}")
        return grouped_requests

    def _format_priority_requests_message(grouped_requests: dict) -> str | None:
        """Вложенная функция для форматирования сообщения."""
        if not any(grouped_requests.values()):
            return None

        message_parts = [hbold("📌 Наиболее приоритетные заявки:") + "\n"]

        if grouped_requests["normal"]:
            message_parts.append(hbold("\nОбычные товары:"))
            message_parts.extend([hcode(req_num) for req_num in grouped_requests["normal"]])
        
        if grouped_requests["clothing"]:
            message_parts.append(hbold("\nОдежда:"))
            message_parts.extend([hcode(req_num) for req_num in grouped_requests["clothing"]])

        if grouped_requests["kgt"]:
            message_parts.append(hbold("\nКГТ:"))
            message_parts.extend([hcode(req_num) for req_num in grouped_requests["kgt"]])

        return "\n".join(message_parts)

    # --- Основной код задачи ---
    logger.info("Запуск задачи по отправке уведомления о приоритетных заявках...")
    try:
        grouped_data = _fetch_and_group_priority_requests()
        message_to_send = _format_priority_requests_message(grouped_data)

        if message_to_send:
            logger.info(f"Отправка сообщения в чат {TARGET_CHAT_ID}...")
            async_task(
                'telegram_bot.tasks.send_message_task',
                chat_id=TARGET_CHAT_ID,
                text=message_to_send,
                parse_mode='HTML'
            )
            logger.info("Задача на отправку сообщения успешно создана.")
        else:
            logger.info("Нет данных для отправки, уведомление не создано.")

    except Exception as e:
        logger.exception("Произошла ошибка в задаче send_priority_strequests_notification:")
        raise e

def _get_google_drive_file_count(service, folder_url: str) -> int | None:
    """
    Возвращает количество файлов в папке Google Drive, используя существующее подключение.
    Поддерживает Общие диски.
    """
    if not folder_url or not isinstance(folder_url, str):
        return 0

    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', folder_url)
    if not match:
        logger.warning(f"Не удалось извлечь ID папки из URL: {folder_url}")
        return None
    folder_id = match.group(1)

    try:
        q = f"'{folder_id}' in parents and trashed = false"
        
        results = service.files().list(
            q=q,
            fields="files(id)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        items = results.get('files', [])
        return len(items)

    except HttpError as error:
        logger.error(f"Ошибка Google Drive API для папки {folder_id}: {error}")
        return None
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при работе с Google Drive для папки {folder_id}: {e}")
        return None


def check_photographer_folders():
    """
    Проверяет папки фотографов на корректность статусов и количество файлов.
    Собирает списки проблемных товаров и отправляет отчет в Telegram.
    """
    logger.info("Запуск задачи проверки папок фотографов...")

    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
    products_to_check = STRequestProduct.objects.filter(
        sphoto_status_id=1,
        senior_check_date__gte=thirty_minutes_ago
    ).select_related('product', 'photo_status')

    if not products_to_check:
        logger.info("Нет продуктов для проверки. Задача завершена.")
        return

    logger.info(f"Найдено {len(products_to_check)} продуктов для проверки.")

    no_folder_list = []
    wrong_status_list = []
    too_few_files_list = []

    try:
        creds = service_account.Credentials.from_service_account_file(
            settings.SERVICE_ACCOUNT_FILE,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        google_service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        logger.exception(f"Критическая ошибка: не удалось подключиться к Google API. {e}")
        return

    for item in products_to_check:
        barcode = item.product.barcode
        photo_status_id = item.photo_status.id if item.photo_status else None
        photos_link = item.photos_link

        if not photos_link:
            no_folder_list.append(hcode(barcode))
            continue

        if photo_status_id is None or photo_status_id == 10:
            wrong_status_list.append(hcode(barcode))
            continue
        
        file_count = _get_google_drive_file_count(google_service, photos_link)
        
        if file_count is None:
            logger.warning(f"Не удалось проверить папку для товара {barcode}: {photos_link}")
            continue

        if photo_status_id == 1 and file_count < 4:
            too_few_files_list.append(f"{hcode(barcode)} - {photos_link}")
        
        elif photo_status_id in [2, 25] and file_count < 1:
            too_few_files_list.append(f"{hcode(barcode)} - {photos_link}")

    if wrong_status_list or too_few_files_list or no_folder_list:
        message_parts = [hbold("🚨 Результаты проверки папок фотографов 🚨\n")]

        if wrong_status_list:
            message_parts.append(hbold("Неправильные статусы:"))
            message_parts.extend(wrong_status_list)
            message_parts.append("")

        if too_few_files_list:
            message_parts.append(hbold("Слишком мало фото:"))
            message_parts.extend(too_few_files_list)
            message_parts.append("")

        if no_folder_list:
            message_parts.append(hbold("Не указана папка:"))
            message_parts.extend(no_folder_list)

        message_text = "\n".join(message_parts)
        
        # --- ПРАВИЛЬНЫЙ ID ЧАТА ДЛЯ ФОТОГРАФОВ ---
        target_chat_id = -1002559221974
        MESSAGE_THREAD_ID = 1519

        logger.info(f"Отправка отчета в чат {target_chat_id}...")
        async_task(
            'telegram_bot.tasks.send_message_task',
            chat_id=target_chat_id,
            text=message_text,
            message_thread_id=MESSAGE_THREAD_ID,
            parse_mode='HTML'
        )
    else:
        logger.info("Проблемных товаров не найдено.")

    logger.info("Задача проверки папок фотографов завершена.")

# +++ КОНЕЦ: ОБНОВЛЕННЫЙ КОД +++

#NOFOTO - Google sheets
def add_nofoto_to_google_sheet(barcode: str, name: str, date_str: str):
    """
    Асинхронная задача для добавления информации о товаре 'Без фото' в Google Таблицу.

    Args:
        barcode (str): Штрихкод товара.
        name (str): Наименование товара.
        date_str (str): Дата в формате 'дд.мм.гггг'.
    """
    logger.info(f"Запуск задачи: добавление ШК {barcode} в Google Sheet 'NoFoto'.")

    SPREADSHEET_ID = '17NWqedOnWSpUROrjWrrqZDxfurqDhJuT4meU2p8mc9s'
    # Укажите имя листа. 'Лист1' - стандартное название. Если у вас другое, измените здесь.
    RANGE_NAME = 'Лист1'
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    try:
        # Аутентификация и создание клиента API
        creds = service_account.Credentials.from_service_account_file(
            settings.SERVICE_ACCOUNT_FILE,
            scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)

        # Данные для добавления в новую строку
        values = [
            [barcode, name, date_str]
        ]
        body = {
            'values': values
        }

        # Вызов API для добавления данных в конец таблицы
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()

        logger.info(f"ШК {barcode} успешно добавлен в Google Sheet. {result.get('updates').get('updatedCells')} ячеек обновлено.")

    except HttpError as error:
        logger.error(f"Произошла ошибка Google Sheets API при добавлении ШК {barcode}: {error}")
    except FileNotFoundError:
        logger.error(f"Критическая ошибка: файл credentials '{settings.SERVICE_ACCOUNT_FILE}' не найден.")
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка в задаче add_nofoto_to_google_sheet для ШК {barcode}: {e}")
