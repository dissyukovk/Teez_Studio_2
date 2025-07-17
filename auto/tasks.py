# myproject/auto/tasks.py
import pytz
import logging
from datetime import datetime, time, timedelta
from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.db import transaction
from django.utils import timezone

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django_q.tasks import async_task
from aiogram.utils.markdown import hbold

from core.models import (
    STRequest,
    STRequestProduct,
    UserProfile,
    RetouchRequest,
    RetouchRequestProduct,
    Product,
    RetouchStatus,
    SRetouchStatus,
    Order,
    OrderProduct,
    ProductCategory
    )
from render.models import Product as RenderProduct

from .models import RGTScripts

import os
import tempfile
import zipfile
import openpyxl
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError # Импорт для обработки ошибок Google API

logger = logging.getLogger(__name__)

# Проверяем количество непроверенных
def check_unverified_photos():
    # Получаем текущее время в часовом поясе Asia/Almaty
    tz = pytz.timezone('Asia/Almaty')
    now = datetime.now(tz).time()

    # Выполняем задачу только с 08:00 до 19:50
    if now < time(8, 0) or now > time(19, 40):
        return

    # Выбираем заявки со статусом = 3
    st_requests = STRequest.objects.filter(status_id=3)
    message_lines = []

    for request in st_requests:
        # Считаем количество продуктов заявки, где photo_status в [1, 2, 25] и sphoto_status != 1.
        products_count = STRequestProduct.objects.filter(
            request=request,
            photo_status_id__in=[1, 2, 25]
        ).exclude(sphoto_status_id=1).count()

        if products_count > 0:
            # Формируем ФИО фотографа. Если фотограф отсутствует, ставим заглушку.
            photographer = request.photographer
            if photographer:
                photographer_name = f"{photographer.first_name} {photographer.last_name}"
            else:
                photographer_name = "Нет фотографа"
            
            message_lines.append(
                f"Заявка {request.RequestNumber} - {photographer_name} - {products_count}"
            )
    
    if not message_lines:
        # Если нет заявок с непроверенными фото, завершаем задачу.
        return

    # Формируем итоговое сообщение
    message_text = "Есть непроверенные фото:\n\n" + "\n".join(message_lines)

    # Получаем пользователей из группы "Старший фотограф" с telegram_id и on_work=True.
    try:
        group = Group.objects.get(name="Старший фотограф")
    except Group.DoesNotExist:
        group = None

    if group:
        # Фильтруем пользователей, у которых telegram_id не пустой и on_work=True.
        users = group.user_set.filter(
            profile__telegram_id__isnull=False,
            profile__telegram_id__gt="",
            profile__on_work=True
        )
        for user in users:
            telegram_id = user.profile.telegram_id
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=telegram_id,
                text=message_text,
            )
            
def check_retoucher_queue():
    # Получаем текущее время в часовом поясе Asia/Almaty
    tz = pytz.timezone('Asia/Almaty')
    now = datetime.now(tz).time()

    # Проверяем, что время между 08:00 и 19:50
    if now < time(8, 0) or now > time(19, 20):
        return

    # Получаем количество записей, удовлетворяющих условиям:
    # photo_status=1, sphoto_status=1 и OnRetouch=False
    queue_count = STRequestProduct.objects.filter(
        photo_status_id=1,
        sphoto_status_id=1,
        OnRetouch=False
    ).count()

    if queue_count > 10:
        try:
            group = Group.objects.get(name="Старший ретушер")
        except Group.DoesNotExist:
            return

        # Фильтруем пользователей с активным статусом работы и заполненным telegram_id
        users = group.user_set.filter(
            profile__on_work=True,
            profile__telegram_id__isnull=False
        ).exclude(profile__telegram_id="")

        # Формируем сообщение
        message_text = f"Очередь на ретушь - {queue_count}"

        # Отправляем сообщение каждому пользователю
        for user in users:
            telegram_id = user.profile.telegram_id
            async_task(
                'telegram_bot.tasks.send_message_task',
                chat_id=telegram_id,
                text=message_text
            )

#Сброс on_work
def reset_on_work_flag():
    updated = UserProfile.objects.filter(on_work=True).update(on_work=False)
    print(f"Reset on_work flag for {updated} user profiles")

# Проверяем все заявки на съемке и переводим в отснятое, отправляем сообщение фотографу.        
def update_strequest_status():
    # Получаем все заявки со статусом 3
    st_requests = STRequest.objects.filter(status_id=3)
    
    for st_request in st_requests:
        # Получаем все связанные записи
        products = STRequestProduct.objects.filter(request=st_request)
        # Если заявке не привязаны продукты, пропускаем её
        if not products.exists():
            continue
        
        all_valid = True
        for product in products:
            # Проверяем, что photo_status не пустой и входит в [1, 2, 25]
            if product.photo_status_id not in [1, 2, 25]:
                all_valid = False
                break
            # Проверяем, что sphoto_status не пустой и равен 1
            if product.sphoto_status_id != 1:
                all_valid = False
                break
        
        # Если для всех продуктов условия выполнены, обновляем статус заявки на 5
        if all_valid:
            st_request.status_id = 5
            # --- Начало добавленных шагов ---
            # 1. Ставим STRequest.check_time = now
            st_request.check_time = timezone.now()
            
            st_request.save() # Сохраняем изменения (status_id и check_time)

            # 2. Отправляем сообщение в телеграм пользователю из поля STRequest.photographer
            photographer = st_request.photographer
            if photographer:
                try:
                    # Пытаемся получить профиль пользователя. 
                    # UserProfile.user - это OneToOneField к User, related_name='profile'
                    user_profile = photographer.profile 
                    if user_profile and user_profile.telegram_id:
                        # Пытаемся получить номер заявки. 
                        # Замените 'RequestNumber' на фактическое имя поля в вашей модели STRequest,
                        # если оно отличается (например, 'number', 'id' и т.д.).
                        request_identifier = getattr(st_request, 'RequestNumber', st_request.id)
                        
                        message_text = f"Заявка {request_identifier} полностью проверена. Можно сдавать."
                        async_task(
                            'telegram_bot.tasks.send_message_task',
                            chat_id=user_profile.telegram_id,
                            text=message_text
                        )
                    else:
                        print(f"У пользователя {photographer.username} отсутствует telegram_id в профиле.")
                except UserProfile.DoesNotExist:
                    print(f"У пользователя {photographer.username} отсутствует профиль UserProfile.")
                except AttributeError as e:
                    # Это может произойти, если у объекта photographer нет атрибута 'profile'
                    # или у st_request нет атрибута 'RequestNumber' (и нет 'id' как запасного)
                    print(f"Ошибка доступа к атрибуту для фотографа {photographer.username} или заявки {st_request.id}: {e}")
            else:
                # Пытаемся получить номер заявки для лога, если фотограф не указан
                request_identifier_log = getattr(st_request, 'RequestNumber', st_request.id)
                print(f"У заявки {request_identifier_log} не указан фотограф (STRequest.photographer is None).")
            # --- Конец добавленных шагов ---

# Поздравление с ДР
def birthday_congratulations():
    # Получаем текущее время в часовом поясе Asia/Almaty
    tz = pytz.timezone('Asia/Almaty')
    now = datetime.now(tz)
    
    # Фильтруем профили, у которых сегодня день и месяц совпадают с birth_date
    birthday_profiles = UserProfile.objects.filter(
        birth_date__day=now.day,
        birth_date__month=now.month
    )
    
    # Чат для отправки поздравления
    chat_id = "-1002177641981"
    
    for profile in birthday_profiles:
        first_name = profile.user.first_name
        last_name = profile.user.last_name
        # Если указан telegram_name, добавляем его с символом @
        telegram_name = f"@{profile.telegram_name}" if profile.telegram_name else ""
        
        message = f"А сегодня день рождения 🎉 празднует {first_name} {last_name}"
        logger.info(f"Attempting to send message for user {profile.user.id}: {message}") # Логирование сообщения
        if telegram_name:
            message += f" - {telegram_name}"
        # Добавляем эмодзи поздравления
        message += " 🎉🎂🥳"
        async_task(
            'telegram_bot.tasks.send_message_task',
            chat_id=chat_id,
            text=message
        )

# Обновление приоритетов у товаров, которые приняты более н дней назад
def update_priority_for_old_incoming_products(): # Изменено: bind=True не нужен для Dramatiq по умолчанию
    """
    Находит товары со статусом 3 (TARGET_MOVE_STATUS_ID),
    у которых дата приемки (income_date) была старше настроенного порога (OldProductsPriorityTreshold),
    и устанавливает для них priority=True, если OldProductsPriorityEnable=True в RGTScripts.
    """
    TASK_NAME = "Скрипт выставления приоритетов по времени приемки"
    # Константы для отправки сообщений, взяты из вашего кода
    GROUP_CHAT_ID = "-1002559221974"
    GROUP_THREAD_ID = 11

    try:
        rgt_settings = RGTScripts.load()  # Загружаем настройки RGTScripts
    except Exception as e:
        logger.error(
            f"Task ({TASK_NAME}) failed to load RGTScripts: {e}", # Изменено
            exc_info=True
        )
        raise  # Перевыбрасываем исключение

    # Проверяем, включен ли функционал
    if not rgt_settings.OldProductsPriorityEnable:
        message = f"{TASK_NAME} - отключен в настройках."
        logger.info(f"Task: {message}") # Изменено
        async_task(
            'telegram_bot.tasks.send_message_task', # Путь к нашей функции
            chat_id=GROUP_CHAT_ID,
            text=message,
            message_thread_id=GROUP_THREAD_ID
        )
        return "Task skipped: OldProductsPriority feature is disabled in RGTScripts."

    # Получаем порог из настроек
    threshold_duration = rgt_settings.OldProductsPriorityTreshold

    # Проверяем, установлен ли порог, если функционал включен
    if threshold_duration is None:
        error_message = (
            f"{TASK_NAME} - Ошибка конфигурации: "
            "Функционал включен (OldProductsPriorityEnable=True), "
            "но порог (OldProductsPriorityTreshold) не установлен в настройках РГТ."
        )
        logger.error(f"Task: {error_message}") # Изменено
        async_task(
            'telegram_bot.tasks.send_message_task', # Путь к нашей функции
            chat_id=GROUP_CHAT_ID,
            text=error_message,
            message_thread_id=GROUP_THREAD_ID
        )
        raise ValueError(error_message)

    # ID статуса для поиска (остается как константа, если не указано иное)
    TARGET_MOVE_STATUS_ID = 3

    try:
        # Рассчитываем пороговую дату, используя DurationField из настроек
        cutoff_date = timezone.now() - threshold_duration

        logger.info(
            f"Starting task: ({TASK_NAME}). " # Изменено
            f"Looking for products with move_status={TARGET_MOVE_STATUS_ID} "
            f"and income_date < {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')} "
            f"(threshold from settings: {threshold_duration})."
        )

        # Находим товары, соответствующие критериям
        products_to_update = Product.objects.filter(
            move_status_id=TARGET_MOVE_STATUS_ID,
            income_date__isnull=False,
            income_date__lt=cutoff_date,
            priority=False  # Оптимизация: обновляем только если priority еще не True
        )

        if products_to_update.exists():
            updated_count = products_to_update.update(priority=True, updated_at=timezone.now())

            logger.info(f"Task ({TASK_NAME}): Successfully set priority=True for {updated_count} products.") # Изменено
            group_message = f"{TASK_NAME} - обновлено {updated_count} SKU."
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=GROUP_CHAT_ID,
                text=group_message,
                message_thread_id=GROUP_THREAD_ID
            )
            return f"Updated priority for {updated_count} products."
        else:
            logger.info(f"Task ({TASK_NAME}): No products found matching the criteria.") # Изменено
            group_message = f"{TASK_NAME} - нет SKU для обновления."
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=GROUP_CHAT_ID,
                text=group_message,
                message_thread_id=GROUP_THREAD_ID
            )
            return "No products needed an update."

    except Exception as e:
        logger.error(f"Task ({TASK_NAME}) failed during execution: {e}", exc_info=True) # Изменено
        raise  # Перевыбрасываем исключение

# Блокировка штрихкодов, которые уже отсняты
def update_render_product_retouch_block_status():
    """
    Находит продукты в ретуши с определенными статусами (retouch_status=2, sretouch_status=1),
    извлекает их баркоды и устанавливает IsRetouchBlock=True для соответствующих
    продуктов в приложении 'render'.
    """
    logger.info("Starting task: update_render_product_retouch_block_status")

    try:
        products_to_process = RetouchRequestProduct.objects.filter(
            retouch_status__id=2,
            sretouch_status__id=1
        ).select_related(
            'st_request_product__product'
        )

        if not products_to_process.exists():
            logger.info("No RetouchRequestProduct found with retouch_status=2 and sretouch_status=1.")
            return "No products found matching the criteria."

        barcodes_to_update = set()
        for rrp in products_to_process:
            if rrp.st_request_product and rrp.st_request_product.product:
                barcodes_to_update.add(rrp.st_request_product.product.barcode)
            else:
                logger.warning(f"RetouchRequestProduct ID {rrp.pk} is missing related st_request_product or product.")

        if not barcodes_to_update:
            logger.info("Found matching RetouchRequestProduct, but could not extract any barcodes.")
            return "Could not extract barcodes from matching products."

        logger.info(f"Found {len(barcodes_to_update)} unique barcodes to check in render.Product: {barcodes_to_update}")

        with transaction.atomic():
            render_products_to_update = RenderProduct.objects.filter(
                Barcode__in=list(barcodes_to_update)
            )

            updated_count = render_products_to_update.update(IsRetouchBlock=True)
            
            group_chat_id = "-1002559221974"
            group_thread_id = 11
            group_message = f"Скрипт блокировки рендеров, где есть готовые фото фс - {updated_count} заблокировано"
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=group_message,
                message_thread_id=group_thread_id
            )
            
            logger.info(f"Successfully set IsRetouchBlock=True for {updated_count} products in render.Product.")

        return f"Task completed. Updated {updated_count} render products."

    except Exception as e:
        logger.error(f"Error during update_render_product_retouch_block_status task: {e}", exc_info=True)
        # Для Dramatiq, если вы хотите повторить задачу, вам нужно будет явно вызвать исключение
        # и настроить middleware Retries на брокере.
        raise # Просто перевыбрасываем исключение, чтобы Dramatiq пометил задачу как неудавшуюся

# Проставить всем IsOnOrder
def update_render_product_is_on_order_status(user_id=None, task_id=None):
    """
    Универсальная задача для обновления статуса IsOnOrder.
    - Выполняет основную логику в любом случае.
    - Отправляет WebSocket уведомление, только если был передан user_id и task_id (ручной запуск).
    """
    logger.info(f"Запуск задачи: update_render_product_is_on_order_status (user_id: {user_id}, task_id: {task_id})")
    final_message = "Произошла неизвестная ошибка."
    
    try:
        reset_count = 0
        update_count = 0
        
        with transaction.atomic():
            reset_count = RenderProduct.objects.filter(IsOnOrder=True).update(IsOnOrder=False)
            
            barcodes_status_2_3 = OrderProduct.objects.filter(order__status_id__in=[2, 3]).values_list('product__barcode', flat=True)
            AcceptTreshold = timezone.now() - timedelta(days=10)
            barcodes_status_4_5_6_accepted = OrderProduct.objects.filter(
                order__status_id__in=[4, 5, 6], accepted=True, accepted_date__gte=AcceptTreshold
            ).values_list('product__barcode', flat=True)

            target_barcodes = set(barcodes_status_2_3) | set(barcodes_status_4_5_6_accepted)

            if not target_barcodes:
                final_message = f"Задача завершена. Сброшено: {reset_count}. Продукты для обновления не найдены."
            else:
                update_count = RenderProduct.objects.filter(
                    Barcode__in=list(target_barcodes), IsOnOrder=False
                ).update(IsOnOrder=True)
                final_message = f"Задача успешно завершена. Сброшено: {reset_count}, Обновлено: {update_count}."

        # Отправка в Telegram работает для обоих типов запуска
        group_chat_id = "-1002559221974"
        group_thread_id = 11
        group_message = f"Статус IsOnOrder обновлен: Сброшено: {reset_count}, Обновлено: {update_count}."
        async_task(
            'telegram_bot.tasks.send_message_task', # Путь к нашей функции
            chat_id=group_chat_id,
            text=group_message,
            message_thread_id=group_thread_id
        )
        
        # --- Блок отправки уведомления по WebSocket ---
        # Сработает, только если был передан user_id и task_id (т.е. при ручном запуске)
        if task_id and user_id:
            logger.info(f"Отправка WS-уведомления для ручного запуска задачи {task_id} пользователю {user_id}")
            channel_layer = get_channel_layer()
            group_name = f'user_task_{user_id}'
            payload = {'status': 'completed', 'message': final_message, 'task_id': task_id}
            
            # Тип сообщения должен соответствовать обработчику в TaskProgressConsumer
            # и содержать вложенную структуру, которую ожидает фронтенд
            async_to_sync(channel_layer.group_send)(
                group_name, {"type": "send.task.progress", "message": {'type': 'completed', 'payload': payload}}
            )

    except Exception as e:
        logger.error(f"Ошибка при выполнении задачи update_render_product_is_on_order_status: {e}", exc_info=True)
        final_message = f'Ошибка выполнения задачи: {e}'
        
        # Если это был ручной запуск, отправляем уведомление об ошибке
        if task_id and user_id:
            channel_layer = get_channel_layer()
            group_name = f'user_task_{user_id}'
            payload = {'status': 'error', 'message': final_message, 'task_id': task_id}
            async_to_sync(channel_layer.group_send)(
                group_name, {"type": "send.task.progress", "message": {'type': 'error', 'payload': payload}}
            )
        # Перевыбрасываем исключение, чтобы задача в Django-Q пометилась как FAILED
        raise

    return final_message


# Обновление базы основной Product
def update_products_from_excel_on_drive(*args, **kwargs):
    """
    Таска для обновления моделей Product и ProductCategory из последнего .xlsx файла в Google Drive.
    """
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    SERVICE_ACCOUNT_FILE = 'credentials.json'
    
    try:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        drive_service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Ошибка аутентификации Google Drive: {e}") # Изменено
        return

    folder_id = '1DMJTs6tUUA6ERkDSDTUYYsYtKHp5yIdv'
    query = (
        f"'{folder_id}' in parents and "
        "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and trashed=false"
    )

    try:
        results = drive_service.files().list(
            q=query,
            fields="files(id, name, modifiedTime)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
    except Exception as e:
        logger.error(f"Ошибка при запросе списка файлов из Google Drive: {e}") # Изменено
        return
        
    items = results.get('files', [])
    if not items:
        logger.warning("Файлы не найдены в указанной папке Google Drive.") # Изменено
        return

    items.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)
    latest_file = items[0]
    file_id = latest_file['id']
    logger.info(f"Загружаем файл: {latest_file['name']} (ID: {file_id}, Modified: {latest_file.get('modifiedTime')})") # Изменено

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
            temp_file_path = temp_file.name
        
        request = drive_service.files().get_media(fileId=file_id)
        with open(temp_file_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Загружено {int(status.progress() * 100)}%.") # Изменено

        with open(temp_file_path, 'rb') as f:
            header = f.read(4)
            logger.debug(f"File header bytes: {header}") # Изменено
        
        if not zipfile.is_zipfile(temp_file_path):
            with open(temp_file_path, 'rb') as f_content:
                file_start_content = f_content.read(100)
            logger.error(f"Файл {latest_file['name']} не является корректным XLSX (не ZIP). Начало содержимого: {file_start_content}") # Изменено
            raise Exception("Скачанный файл не является корректным XLSX (не распознается как ZIP-архив).")

        with zipfile.ZipFile(temp_file_path, 'r') as archive:
            logger.debug("Содержимое архива XLSX:") # Изменено
            for file_in_archive in archive.namelist():
                logger.debug(file_in_archive) # Изменено
        
        wb = openpyxl.load_workbook(temp_file_path, data_only=True)
        ws = wb.active

        for row_index, row in enumerate(ws.iter_rows(min_row=2), start=2):
            try:
                barcode_val = row[0].value
                if barcode_val is None or str(barcode_val).strip() == "":
                    logger.warning(f"Строка {row_index}: Пропущен пустой баркод.") # Изменено
                    continue
                barcode = str(barcode_val).strip()

                product_id_val = row[1].value
                product_id = int(product_id_val) if product_id_val is not None else None
                
                skuid_val = row[2].value
                skuid = int(skuid_val) if skuid_val is not None else None
                
                product_name = str(row[3].value).strip() if row[3].value is not None else ""

                category_id_val = row[4].value
                category_id = int(category_id_val) if category_id_val is not None else None

                product_ShopType = str(row[5].value).strip() if row[5].value is not None else ""
                
                category_name_val = row[6].value
                category_name = str(category_name_val).strip() if category_name_val is not None else None
                
                seller_val = row[7].value
                seller = int(seller_val) if seller_val is not None else None

                product_ShopName = str(row[8].value).strip() if row[8].value is not None else ""

                product_ProductStatus = str(row[9].value).strip() if row[9].value is not None else ""

                product_ProductModerationStatus = str(row[10].value).strip() if row[10].value is not None else ""

                product_PhotoModerationStatus = str(row[11].value).strip() if row[11].value is not None else ""

                product_SKUStatus = str(row[12].value).strip() if row[12].value is not None else ""
                
                in_stock_sum_val = row[14].value 
                in_stock_sum = int(in_stock_sum_val) if in_stock_sum_val is not None else 0

                category_instance = None
                if category_id is not None:
                    category_defaults = {}
                    if category_name:
                         category_defaults['name'] = category_name
                    
                    category_instance, created = ProductCategory.objects.update_or_create(
                        id=category_id,
                        defaults=category_defaults
                    )
                    if created:
                        logger.info(f"Создана категория: ID={category_id}, Name='{category_name}'") # Изменено
                    elif category_defaults.get('name') and category_instance.name != category_defaults['name']:
                        logger.info(f"Обновлено имя категории: ID={category_id}, New Name='{category_name}', Old Name='{category_instance.name}'") # Изменено
                else:
                    logger.warning(f"Строка {row_index}, Баркод {barcode}: ID категории не указан. Продукт будет без категории.") # Изменено

                product_data_for_update = {
                    'ProductID': product_id,
                    'SKUID': skuid,
                    'name': product_name,
                    'category': category_instance,
                    'seller': seller,
                    'in_stock_sum': in_stock_sum,
                    'ShopType': product_ShopType,
                    'ShopName': product_ShopName,
                    'ProductStatus': product_ProductStatus,
                    'ProductModerationStatus': product_ProductModerationStatus,
                    'PhotoModerationStatus': product_PhotoModerationStatus,
                    'SKUStatus': product_SKUStatus,
                }
                
                product_obj, created = Product.objects.update_or_create(
                    barcode=barcode,
                    defaults=product_data_for_update
                )

            except ValueError as ve:
                logger.error(f"Ошибка конвертации данных в строке {row_index}: {ve}. Пропускаем строку. Данные: {row_values(row)}") # Изменено
            except Exception as e:
                logger.error(f"Общая ошибка при обработке строки {row_index} с баркодом '{barcode_val}': {e}. Данные: {row_values(row)}") # Изменено

        group_chat_id = "-1002559221974"
        group_thread_id = 11
        group_message = "Обновление базы продуктов завершено"
        async_task(
            'telegram_bot.tasks.send_message_task', # Путь к нашей функции
            chat_id=group_chat_id,
            text=group_message,
            message_thread_id=group_thread_id
        )
        
        logger.info("Обновление базы продуктов завершено.") # Изменено

    except FileNotFoundError:
        logger.error(f"Файл credentials.json не найден по пути {SERVICE_ACCOUNT_FILE}.") # Изменено
    except Exception as e:
        logger.error(f"Произошла ошибка во время выполнения задачи: {e}") # Изменено
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Временный файл {temp_file_path} удален.") # Изменено
            except Exception as e:
                logger.error(f"Не удалось удалить временный файл {temp_file_path}: {e}") # Изменено

def row_values(row):
    """Вспомогательная функция для логирования значений строки."""
    return [cell.value for cell in row]

#Обертка для update_products_from_excel_on_drive
def update_products_from_excel_on_drive_custom_timeout():
    """
    Запускает обновление базы продуктов с таймаутом 15 минут.
    Именно эту задачу нужно указывать в Cron-расписании в админке.
    """
    logger.info("Запуск 'update_products_from_excel_on_drive' через обертку с таймаутом 900с")
    async_task(
        'auto.tasks.update_products_from_excel_on_drive',  # Путь к реальной задаче
        timeout=900,   # 15 минут
        retry=1000,    # Повтор через 20 минут, если задача упадет
        attempts=2     # Попробовать 3 раза
    )


## Запись текущих товаров со статусами
def write_product_stats_to_google_sheet():
    """
    Calculates product statistics and writes them as a new row to a Google Sheet.
    """
    logger.info("Starting task: write_product_stats_to_google_sheet")

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    SERVICE_ACCOUNT_FILE = 'credentials.json'
    SPREADSHEET_ID = '1l4QwwORix970J-FUiYYxGfdXtVsejLoqLvq8g6EwsYw'
    
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
    except FileNotFoundError:
        logger.error(f"Authentication error: '{SERVICE_ACCOUNT_FILE}' not found.")
        return "Task failed: Credentials file not found."
    except Exception as e:
        logger.error(f"An error occurred during Google API authentication: {e}")
        return f"Task failed: {e}"

    try:
        all_products = Product.objects.all()
        products_in_stock = all_products.filter(in_stock_sum__gt=0)
        
        blocked_status_query = Q(ProductModerationStatus='Заблокирован') | Q(SKUStatus='Заблокирован')

        total_count = all_products.count()
        
        blocked_count = all_products.filter(blocked_status_query).distinct().count()
        
        passed_moderation_count = all_products.filter(PhotoModerationStatus="Прошло модерацию").count()
        in_moderation_count = all_products.filter(PhotoModerationStatus="На модерации").count()
        rejected_moderation_count = all_products.filter(PhotoModerationStatus="Отклонено").count()
        
        in_stock_count = products_in_stock.count()
        
        blocked_in_stock_count = products_in_stock.filter(blocked_status_query).distinct().count()
        passed_moderation_in_stock_count = products_in_stock.filter(PhotoModerationStatus="Прошло модерацию").count()
        in_moderation_in_stock_count = products_in_stock.filter(PhotoModerationStatus="На модерации").count()
        rejected_moderation_in_stock_count = products_in_stock.filter(PhotoModerationStatus="Отклонено").count()

        current_date = datetime.now().strftime('%d.%m.%Y')

        row_data = [
            current_date,
            total_count,
            blocked_count,
            passed_moderation_count,
            in_moderation_count,
            rejected_moderation_count,
            in_stock_count,
            blocked_in_stock_count,
            passed_moderation_in_stock_count,
            in_moderation_in_stock_count,
            rejected_moderation_in_stock_count
        ]
        
        logger.info(f"Calculated stats for {current_date}: {row_data[1:]}")

    except Exception as e:
        logger.error(f"Error during data calculation from Django models: {e}", exc_info=True)
        return f"Task failed during data calculation: {e}"

    try:
        body = {
            'values': [row_data]
        }
        result = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range='Лист1!A1',
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        logger.info(f"Successfully appended data to Google Sheet. Result: {result.get('updates').get('updatedRange')}")
        return f"Task completed successfully. Appended to {result.get('updates').get('updatedRange')}."

    except HttpError as err:
        logger.error(f"An HTTP error occurred while writing to Google Sheets: {err}", exc_info=True)
        return f"Task failed: {err}"
    except Exception as e:
        logger.error(f"An unexpected error occurred while writing to Google Sheets: {e}", exc_info=True)
        return f"Task failed: {e}"

#Выгрузка для Жени
def export_recent_products_to_sheet():
    """
    Выгружает данные по товарам с датой приемки за последние 7 дней в Google Таблицу.
    Предварительно полностью очищает лист 'data'. Даты конвертируются в формат ISO 8601.
    """
    logger.info("Запуск задачи: export_recent_products_to_sheet (с конвертацией дат в ISO)")

    # --- Настройки доступа к Google API ---
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    SERVICE_ACCOUNT_FILE = 'credentials.json'
    SPREADSHEET_ID = '1K5YkeQPD0f4j3yfnzg26PJqfICqhFlY7bcJuYPJvNo4'
    SHEET_NAME = 'data'

    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
    except FileNotFoundError:
        logger.error(f"Ошибка аутентификации: файл '{SERVICE_ACCOUNT_FILE}' не найден.")
        return "Task failed: Credentials file not found."
    except Exception as e:
        logger.error(f"Произошла ошибка при аутентификации Google API: {e}", exc_info=True)
        return f"Task failed: {e}"

    try:
        # --- 1. Очистка листа ---
        logger.info(f"Очистка листа '{SHEET_NAME}'...")
        sheet.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_NAME,
            body={}
        ).execute()
        logger.info("Лист успешно очищен.")

        # --- 2. Получение и обработка данных ---
        logger.info("Получение продуктов из базы данных...")
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        products = Product.objects.filter(
            income_date__gte=seven_days_ago
        ).select_related('move_status').prefetch_related(
            'strequestproduct_set__request'
        )
        
        logger.info(f"Найдено {products.count()} продуктов для выгрузки.")

        header = [
            'SKUID', 'Barcode', 'Income_date', 'check_time', 
            'outcome_date', 'move_status_id', 'move_status_name'
        ]
        rows_to_write = [header]

        for product in products:
            # --- Поиск последнего check_time ---
            latest_check_time = None
            if product.income_date:
                for srp in product.strequestproduct_set.all():
                    st_request = srp.request
                    if st_request and st_request.check_time and st_request.check_time > product.income_date:
                        if latest_check_time is None or st_request.check_time > latest_check_time:
                            latest_check_time = st_request.check_time
            
            # --- Проверка outcome_date ---
            final_outcome_date = None
            if product.income_date and product.outcome_date and product.outcome_date > product.income_date:
                final_outcome_date = product.outcome_date

            # --- ИСПРАВЛЕНИЕ: Конвертация datetime в строку формата ISO ---
            # Этот формат является JSON-сериализуемым и корректно распознается Google Sheets.
            income_date_iso = product.income_date.isoformat() if product.income_date else ""
            check_time_iso = latest_check_time.isoformat() if latest_check_time else ""
            outcome_date_iso = final_outcome_date.isoformat() if final_outcome_date else ""
            
            row_data = [
                product.SKUID,
                product.barcode,
                income_date_iso,
                check_time_iso,
                outcome_date_iso,
                product.move_status.id if product.move_status else None,
                product.move_status.name if product.move_status else None
            ]
            rows_to_write.append(row_data)

        # --- 3. Запись данных в таблицу ---
        if len(rows_to_write) > 1:
            logger.info(f"Запись {len(rows_to_write) - 1} строк в Google Sheet...")
            body = {'values': rows_to_write}
            result = sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{SHEET_NAME}!A1',
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            logger.info(f"Данные успешно записаны. Обновленный диапазон: {result.get('updatedRange')}")
        else:
            logger.info("Нет данных для выгрузки, будет записан только заголовок.")
            body = {'values': [header]}
            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{SHEET_NAME}!A1',
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            logger.info("Заголовок успешно записан.")
        
        return f"Задача успешно завершена. Обработано {len(rows_to_write) - 1} продуктов."

    except HttpError as err:
        logger.error(f"Произошла ошибка HTTP при работе с Google Sheets: {err}", exc_info=True)
        return f"Task failed: {err}"
    except Exception as e:
        logger.error(f"Произошла непредвиденная ошибка при выполнении задачи: {e}", exc_info=True)
        # Перевыбрасываем исключение, чтобы Django-Q мог его обработать
        raise
