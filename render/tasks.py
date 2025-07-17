#render/tasks.py
import os
import tempfile
import openpyxl
import zipfile
import logging
import io
import datetime
import re
from django_q.tasks import async_task
from datetime import timedelta, time
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from googleapiclient.errors import HttpError
from django.contrib.auth.models import User, Group
from .models import (
    Product,
    ModerationUpload,
    ModerationStudioUpload,
    Render,
    UploadStatus,
    RejectedReason,
    RetouchStatus,
    StudioRejectedReason
    )
from core.models import (
    Product as CoreProduct,
    RetouchRequestProduct,
    STRequestProduct
    )

from .serializers import (
    RetoucherRenderSerializer,
    SeniorRenderSerializer,
    ModerationUploadRejectSerializer,
    ModerationStudioUploadSerializer,
    ModerationUploadSerializer
    )


logger = logging.getLogger(__name__)

#Вспомогательная функция экранирования сообщений в телеграм
def escape_markdown(text: str) -> str:
    """
    Экранирует специальные символы в тексте для безопасной отправки
    в Telegram с parse_mode='MarkdownV2'.
    """
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*[]()~`>#+-.=|{}!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


#Обновление таблицы с продуктами
def update_products_from_drive(*args, **kwargs):
    """
    Таска для обновления модели Product из последнего .xlsx файла в Google Drive.
    """
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=creds)

    folder_id = '1DMJTs6tUUA6ERkDSDTUYYsYtKHp5yIdv'
    query = (
        f"'{folder_id}' in parents and "
        "mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and trashed=false"
    )

    results = drive_service.files().list(
        q=query,
        fields="files(id, name, modifiedTime)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute()
    items = results.get('files', [])
    if not items:
        print("Файлы не найдены.")
        return

    # Сортируем файлы по modifiedTime по убыванию и выбираем последний
    items.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)
    latest_file = items[0]
    file_id = latest_file['id']
    print(f"Загружаем файл: {latest_file['name']} (ID: {file_id})")

    # Создаем временный файл с расширением .xlsx
    temp_file = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    request = drive_service.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(temp_file, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"Загружено {int(status.progress() * 100)}%.")
    temp_file.close()

    # Диагностика: выводим заголовок и содержимое архива
    with open(temp_file.name, 'rb') as f:
        header = f.read(4)
        print("File header bytes:", header)
    with zipfile.ZipFile(temp_file.name, 'r') as archive:
        print("Содержимое архива XLSX:")
        for file in archive.namelist():
            print(file)
    if not zipfile.is_zipfile(temp_file.name):
        raise Exception("Скачанный файл не является корректным XLSX (не распознается как ZIP-архив).")

    # Загружаем книгу
    wb = openpyxl.load_workbook(temp_file.name, data_only=True)
    ws = wb.active

    # Обрабатываем строки, начиная со второй (первая – заголовок)
    for row_index, row in enumerate(ws.iter_rows(min_row=2), start=2):
        barcode = row[0].value  # Столбец B
        # Если Barcode пустое или состоит только из пробелов, пропускаем эту строчку
        if not barcode or not str(barcode).strip():
            continue

        product_data = {
            'ProductID': int(row[1].value) if row[1].value is not None else None,
            'SKUID': int(row[2].value) if row[2].value is not None else None,
            'Name': row[3].value,
            'CategoryName': row[6].value,
            'ShopID': int(row[7].value) if row[7].value is not None else None,
            'CategoryID': int(row[4].value) if row[4].value is not None else None,
            'ShopType': row[5].value,
            'ShopName': row[8].value,
            'ProductStatus': row[9].value,
            'ProductModerationStatus': row[10].value,
            'PhotoModerationStatus': row[11].value,
            'SKUStatus': row[12].value,
            'WMSQuantity': int(row[14].value) if row[14].value is not None else None,
        }

        try:
            Product.objects.update_or_create(Barcode=barcode, defaults=product_data)
        except Exception as e:
            print(f"Ошибка при обработке строки {row_index} с Barcode {barcode}: {e}")

    group_chat_id = "-1002559221974"
    group_thread_id = 11
    group_message = f"Обновление базы рендеров - завершено"
    async_task(
        'telegram_bot.tasks.send_message_task', # Путь к нашей функции
        chat_id=group_chat_id,
        text=group_message,
        message_thread_id=group_thread_id
    )

    os.remove(temp_file.name)
    print("Обновление завершено.")

#Обертка для update_products_from_drive
def update_products_from_drive_custom_timeout():
    """
    Запускает обновление базы продуктов с таймаутом 15 минут.
    Именно эту задачу нужно указывать в Cron-расписании в админке.
    """
    logger.info("Запуск 'update_products_from_excel_on_drive' через обертку с таймаутом 900с")
    async_task(
        'render.tasks.update_products_from_drive',  # Путь к реальной задаче
        timeout=900,   # 15 минут
        retry=1000,    # Повтор через 20 минут, если задача упадет
        attempts=2     # Попробовать 3 раза
    )

#сброс рендеров на этапе проверки или без статуса
def update_renders_and_products_status():
    """
    Находит все объекты Render со статусом RetouchStatus=1 ИЛИ без статуса (NULL),
    меняет их статус на 10 и устанавливает IsOnRender=False
    для связанных объектов Product.
    """
    # ID статусов, которые мы ищем и на которые меняем
    # Лучше хранить их в константах или получать из базы, если они могут меняться
    SOURCE_RETOUCH_STATUS_ID = 1
    TARGET_RETOUCH_STATUS_ID = 10

    # Проверяем, существует ли целевой статус в базе данных, чтобы избежать ошибок FK
    try:
        target_status = RetouchStatus.objects.get(id=TARGET_RETOUCH_STATUS_ID)
    except RetouchStatus.DoesNotExist:
        logger.error(f"Целевой RetouchStatus с ID={TARGET_RETOUCH_STATUS_ID} не найден в базе данных. Задача прервана.")
        return f"Error: Target RetouchStatus ID={TARGET_RETOUCH_STATUS_ID} not found."

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    # Выбираем все объекты Render с нужным статусом ИЛИ где статус NULL
    renders_to_update_qs = Render.objects.filter(
        Q(RetouchStatus_id=SOURCE_RETOUCH_STATUS_ID) | Q(RetouchStatus_id__isnull=True)
    )
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    # Получаем список ID связанных Product объектов.
    # values_list('Product_id', flat=True) эффективнее, чем перебирать queryset в цикле
    product_ids_to_update = list(renders_to_update_qs.values_list('Product_id', flat=True))

    if not product_ids_to_update:
        # Можно немного обновить сообщение для ясности
        message = (f"Не найдено Render объектов со статусом RetouchStatus ID={SOURCE_RETOUCH_STATUS_ID} "
                   f"или без статуса для обновления.")
        logger.info(message)
        return message

    updated_renders_count = 0
    updated_products_count = 0

    try:
        # Используем транзакцию, чтобы гарантировать атомарность операции:
        # Либо все обновления пройдут успешно, либо ни одно не применится.
        with transaction.atomic():
            # 1. Обновляем связанные Product объекты
            # Используем update() для массового обновления одним SQL запросом - это эффективно
            updated_products_count = Product.objects.filter(
                id__in=product_ids_to_update
            ).update(IsOnRender=False)

            # 2. Обновляем сами Render объекты
            # Также используем update() для эффективности
            # Используем тот же queryset, который выбрали изначально
            updated_renders_count = renders_to_update_qs.update(
                RetouchStatus_id=TARGET_RETOUCH_STATUS_ID
            )

        success_message = (f"Успешно обновлено {updated_renders_count} Render объектов "
                           f"(статус изменен на ID={TARGET_RETOUCH_STATUS_ID}) и "
                           f"{updated_products_count} Product объектов (IsOnRender установлен в False).")
        logger.info(success_message)
        return success_message

    except Exception as e:
        # Логируем ошибку, если что-то пошло не так во время транзакции
        error_message = f"Ошибка во время выполнения задачи update_renders_and_products_status: {e}"
        logger.exception(error_message) # logger.exception включает traceback
        # Перевыбрасываем исключение, чтобы Dramatiq мог обработать его согласно своей конфигурации (например, повторить попытку)
        raise e

#Сброс незавершенных загрузок модерации
def update_moderation_uploads_status():
    """
    Находит все объекты ModerationUpload и ModerationStudioUpload
    со статусом UploadStatus=1 ИЛИ без статуса (NULL), меняет их статус на 4.
    Также устанавливает IsOnUpload=False для связанных объектов
    Render (для ModerationUpload) и RetouchRequestProduct (для ModerationStudioUpload).
    """
    SOURCE_UPLOAD_STATUS_ID = 1
    TARGET_UPLOAD_STATUS_ID = 4

    # Проверяем, существует ли целевой статус UploadStatus в базе данных
    try:
        target_status = UploadStatus.objects.get(id=TARGET_UPLOAD_STATUS_ID)
    except UploadStatus.DoesNotExist:
        logger.error(f"Целевой UploadStatus с ID={TARGET_UPLOAD_STATUS_ID} не найден в базе данных. Задача прервана.")
        return f"Error: Target UploadStatus ID={TARGET_UPLOAD_STATUS_ID} not found."

    # Инициализируем счетчики обновленных записей
    updated_mod_uploads_count = 0
    updated_renders_count = 0
    updated_studio_uploads_count = 0
    updated_retouch_prods_count = 0

    try:
        # Используем одну транзакцию для всех обновлений, чтобы гарантировать консистентность
        with transaction.atomic():

            # --- Обработка ModerationUpload ---
            # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
            mod_uploads_to_update_qs = ModerationUpload.objects.filter(
                Q(UploadStatus_id=SOURCE_UPLOAD_STATUS_ID) | Q(UploadStatus_id__isnull=True)
            )
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---

            # Получаем ID связанных Render объектов
            render_ids_to_update = list(mod_uploads_to_update_qs.values_list('RenderPhotos_id', flat=True))

            if render_ids_to_update: # Проверяем именно наличие ID, так как queryset может быть непустым, но без ссылок
                # Обновляем связанные Render объекты
                updated_renders_count = Render.objects.filter(
                    id__in=render_ids_to_update
                ).update(IsOnUpload=False)

                # Обновляем сами ModerationUpload объекты
                updated_mod_uploads_count = mod_uploads_to_update_qs.update(
                    UploadStatus_id=TARGET_UPLOAD_STATUS_ID
                )
                logger.info(f"Обработано {updated_mod_uploads_count} ModerationUpload записей (статус {SOURCE_UPLOAD_STATUS_ID} или NULL).")
            # Добавим elif для случая, когда есть записи, но нет связанных Render ID
            elif mod_uploads_to_update_qs.exists():
                 # Если есть записи ModerationUpload, но нет связанных Render ID,
                 # все равно обновим их статус
                 updated_mod_uploads_count = mod_uploads_to_update_qs.update(
                     UploadStatus_id=TARGET_UPLOAD_STATUS_ID
                 )
                 logger.info(f"Обработано {updated_mod_uploads_count} ModerationUpload записей (статус {SOURCE_UPLOAD_STATUS_ID} или NULL) без связанных Render.")
            else:
                logger.info(f"Не найдено ModerationUpload записей со статусом ID={SOURCE_UPLOAD_STATUS_ID} или NULL.")


            # --- Обработка ModerationStudioUpload ---
            # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
            studio_uploads_to_update_qs = ModerationStudioUpload.objects.filter(
                 Q(UploadStatus_id=SOURCE_UPLOAD_STATUS_ID) | Q(UploadStatus_id__isnull=True)
            )
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---

            # Получаем ID связанных RetouchRequestProduct объектов
            retouch_prod_ids_to_update = list(studio_uploads_to_update_qs.values_list('RenderPhotos_id', flat=True))

            if retouch_prod_ids_to_update: # Проверяем наличие ID
                # Обновляем связанные RetouchRequestProduct объекты
                updated_retouch_prods_count = RetouchRequestProduct.objects.filter(
                    id__in=retouch_prod_ids_to_update
                ).update(IsOnUpload=False)

                # Обновляем сами ModerationStudioUpload объекты
                updated_studio_uploads_count = studio_uploads_to_update_qs.update(
                    UploadStatus_id=TARGET_UPLOAD_STATUS_ID
                )
                logger.info(f"Обработано {updated_studio_uploads_count} ModerationStudioUpload записей (статус {SOURCE_UPLOAD_STATUS_ID} или NULL).")
            # Добавим elif для случая, когда есть записи, но нет связанных RetouchRequestProduct ID
            elif studio_uploads_to_update_qs.exists():
                updated_studio_uploads_count = studio_uploads_to_update_qs.update(
                    UploadStatus_id=TARGET_UPLOAD_STATUS_ID
                )
                logger.info(f"Обработано {updated_studio_uploads_count} ModerationStudioUpload записей (статус {SOURCE_UPLOAD_STATUS_ID} или NULL) без связанных RetouchRequestProduct.")
            else:
                logger.info(f"Не найдено ModerationStudioUpload записей со статусом ID={SOURCE_UPLOAD_STATUS_ID} или NULL.")

        # Формируем итоговое сообщение после успешного завершения транзакции
        success_message = (
            f"Завершено обновление статусов загрузки (статус {SOURCE_UPLOAD_STATUS_ID} или NULL -> {TARGET_UPLOAD_STATUS_ID}). "
            f"ModerationUpload: {updated_mod_uploads_count} записей обновлено, "
            f"{updated_renders_count} связанных Render обновлено (IsOnUpload=False). "
            f"ModerationStudioUpload: {updated_studio_uploads_count} записей обновлено, "
            f"{updated_retouch_prods_count} связанных RetouchRequestProduct обновлено (IsOnUpload=False)."
        )
        logger.info(success_message)
        return success_message

    except Exception as e:
        # Логируем ошибку, если что-то пошло не так во время транзакции
        error_message = f"Ошибка во время выполнения задачи update_moderation_uploads_status: {e}"
        logger.exception(error_message) # logger.exception включает traceback
        # Перевыбрасываем исключение для обработки Dramatiq
        raise e

#отправить загруженные блоки модерации
def check_uploads_for_blocked_products(): # Убран self из параметров
    """
    Проверяет загрузки студийных фото (ModerationStudioUpload), завершенные
    в определенный временной интервал, извлекает их баркоды и проверяет
    статус связанных товаров (Product). Если найдены товары со статусом
    "Заблокирован" (ProductModerationStatus или SKUStatus), отправляет
    список их баркодов в Telegram.
    """
    # task_id = self.request.id # Эта строка будет удалена, так как нет self.request.id в Dramatiq
    # Вместо task_id можно сгенерировать уникальный ID, если очень нужен
    # Например, import uuid; task_id = str(uuid.uuid4())
    task_id = "check_blocked_products_task" # Пример заглушки для логирования

    UPLOAD_COMPLETED_STATUS_ID = 2
    TARGET_CHAT_ID = "-1002513626060" # Убедись, что это правильный ID чата
    BLOCKED_PRODUCT_STATUS = "Заблокирован"
    BLOCKED_SKU_STATUS = "Заблокирован" # Используем два разных статуса

    logger.info(f"[{task_id}] Запуск задачи check_uploads_for_blocked_products...")

    try:
        # 1. Определяем временной интервал в зависимости от ЛОКАЛЬНОГО времени
        now_utc = timezone.now()
        try:
            local_tz = timezone.get_current_timezone()
            now_local = now_utc.astimezone(local_tz)
            logger.info(f"[{task_id}] Время UTC: {now_utc}, Время локальное ({local_tz}): {now_local}")
        except Exception as tz_error:
            logger.error(f"[{task_id}] Ошибка при получении/конвертации таймзоны: {tz_error}. Используется UTC.")
            now_local = now_utc # Fallback

        current_hour = now_local.hour
        start_time = None
        end_time = None
        today = now_local.date()
        yesterday = today - timedelta(days=1)

        # Определяем временные окна (используем твои последние значения 6-10 и 15-18)
        if 6 <= current_hour < 10: # Утреннее окно
            start_time = timezone.make_aware(timezone.datetime.combine(yesterday, time(16, 0, 0)), local_tz)
            end_time = timezone.make_aware(timezone.datetime.combine(today, time(8, 0, 0)), local_tz)
            logger.info(f"[{task_id}] Утренний запуск (локальный час {current_hour}): Проверка интервала UploadTimeEnd с {start_time} по {end_time}")
        elif 15 <= current_hour < 18: # Дневное окно
            start_time = timezone.make_aware(timezone.datetime.combine(today, time(8, 0, 0)), local_tz)
            end_time = timezone.make_aware(timezone.datetime.combine(today, time(16, 0, 0)), local_tz)
            logger.info(f"[{task_id}] Дневной запуск (локальный час {current_hour}): Проверка интервала UploadTimeEnd с {start_time} по {end_time}")
        else:
            logger.warning(f"[{task_id}] Задача запущена в не предназначенное время (локальное время {now_local}, час={current_hour}). Проверка не выполняется.")
            return f"Задача {task_id} запущена вне запланированного окна по локальному времени {local_tz}."

        # 2. Находим ModerationStudioUpload, завершенные в интервале, с нужным статусом
        logger.info(f"[{task_id}] Поиск ModerationStudioUpload: StatusID={UPLOAD_COMPLETED_STATUS_ID}, UploadTimeEnd>={start_time}, UploadTimeEnd<{end_time}")
        recent_uploads_qs = ModerationStudioUpload.objects.filter(
            UploadStatus_id=UPLOAD_COMPLETED_STATUS_ID,
            UploadTimeEnd__gte=start_time,
            UploadTimeEnd__lt=end_time
        )

        # Оптимизация: используем values_list для получения только нужных полей для баркода
        # Путь должен быть точным! Проверь его по своим моделям.
        # Если путь сложный, select_related может быть все еще нужен перед values_list,
        # но values_list с __ доступом часто эффективнее.
        barcode_related_path = 'RenderPhotos__st_request_product__product__barcode'
        upload_ids_and_barcodes = list(recent_uploads_qs.values_list('id', barcode_related_path))

        logger.info(f"[{task_id}] Найдено {len(upload_ids_and_barcodes)} записей ModerationStudioUpload, подходящих по времени и статусу.")

        if not upload_ids_and_barcodes:
            logger.info(f"[{task_id}] Нет загрузок для дальнейшей проверки.")
            return f"[{task_id}] Нет загрузок для проверки в интервале {start_time.strftime('%Y-%m-%d %H:%M')} - {end_time.strftime('%Y-%m-%d %H:%M')}."

        # 3. Собираем уникальные баркоды из найденных загрузок
        barcodes_to_check = set()
        logger.info(f"[{task_id}] Начинаем сбор баркодов...")
        for upload_id, barcode in upload_ids_and_barcodes:
            if barcode:
                barcodes_to_check.add(barcode)
                # Лог ниже может быть слишком подробным, если записей много
                # logger.debug(f"[{task_id}] Upload ID {upload_id}: Извлечен баркод {barcode}")
            else:
                logger.warning(f"[{task_id}] Upload ID {upload_id}: Баркод пустой или None.")
        logger.info(f"[{task_id}] Сбор баркодов завершен. Уникальных баркодов для проверки: {len(barcodes_to_check)}. Баркоды: {barcodes_to_check if len(barcodes_to_check) < 50 else str(list(barcodes_to_check)[:50]) + '...'}") # Логируем только часть если много

        if not barcodes_to_check:
            logger.info(f"[{task_id}] Не найдено валидных баркодов в обработанных загрузках.")
            return f"[{task_id}] Баркоды не извлечены из найденных загрузок."

        # 4. Ищем товары (Product) по баркодам и проверяем их статусы
        logger.info(f"[{task_id}] Поиск Product со статусами '{BLOCKED_PRODUCT_STATUS}' или '{BLOCKED_SKU_STATUS}' и баркодами из списка: {list(barcodes_to_check)}")

        blocked_products_qs = Product.objects.filter(
            Q(ProductModerationStatus=BLOCKED_PRODUCT_STATUS) | Q(SKUStatus=BLOCKED_SKU_STATUS),
            Barcode__in=list(barcodes_to_check) # Передаем список баркодов
        )

        # Получаем только уникальные баркоды заблокированных товаров
        blocked_barcodes = list(blocked_products_qs.values_list('Barcode', flat=True).distinct())
        logger.info(f"[{task_id}] Найдено {len(blocked_barcodes)} заблокированных баркодов: {blocked_barcodes}")

        # 5. Если найдены заблокированные товары, отправляем сообщение
        if blocked_barcodes:
            logger.warning(f"[{task_id}] Обнаружены загрузки для заблокированных товаров/SKU: {blocked_barcodes}")
            # Формируем сообщение
            header_text = f"‼️ Загружены фото для заблокированных КТ/SKU ({start_time.strftime('%d.%m %H:%M')} - {end_time.strftime('%d.%m %H:%M')}):"
            message_lines = [
                escape_markdown(header_text) # <--- ИСПОЛЬЗУЕМ ЭКРАНИРОВАНИЕ
            ]
            message_lines.extend([f"`{barcode}`" for barcode in blocked_barcodes]) # Баркоды в обратных кавычках экранировать не нужно
            final_message = "\n".join(message_lines)

            # Отправляем сообщение
            try:
                async_task(
                    'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                    chat_id=TARGET_CHAT_ID,
                    text=final_message,
                    parse_mode='MarkdownV2'
                )
                logger.info(f"[{task_id}] Уведомление о {len(blocked_barcodes)} заблокированных товарах отправлено в чат {TARGET_CHAT_ID}.")
                # Возвращаем сообщение об успехе
                return f"[{task_id}] Отправлено уведомление о {len(blocked_barcodes)} заблокированных товарах."
            except Exception as telegram_error:
                logger.error(f"[{task_id}] Ошибка отправки сообщения в Telegram (чат {TARGET_CHAT_ID}): {telegram_error}")
                # Возвращаем сообщение об ошибке отправки
                return f"[{task_id}] Ошибка отправки сообщения в Telegram: {telegram_error}"
        else:
            # Если заблокированных товаров не найдено
            logger.info(f"[{task_id}] Не найдено заблокированных товаров среди продуктов с баркодами из недавних загрузок.")
            # Возвращаем сообщение об отсутствии заблокированных товаров
            return f"[{task_id}] Заблокированные товары не найдены в проверенном интервале."

    except Exception as e:
        # Ловим любые другие ошибки во время выполнения задачи
        logger.exception(f"[{task_id}] Произошла непредвиденная ошибка при выполнении задачи check_uploads_for_blocked_products:")
        # Возвращаем общее сообщение об ошибке
        # В Dramatiq, чтобы пометить задачу как FAILED, нужно просто вызвать исключение
        raise e


#Выгрузка для аналитики по конверсии
# --- Настройки Google Drive определены прямо здесь ---
# ВАЖНО: Укажите правильный путь к вашему файлу credentials.json
GOOGLE_CREDENTIALS_FILE_PATH = 'credentials.json'
credentials_path = 'credentials.json' # 👈 **ОБНОВИТЕ ЭТОТ ПУТЬ**
# ID таблицы бщей папки на Google Drive
TARGET_SPREADSHEET_ID = '1hxfxiuP8PbshJVGZhgXPijOEaa9J-R5PuN1ghn3O2Zo'
TARGET_SHEET_NAME = 'data'
# Области доступа для API Google Drive (для создания файлов)
GOOGLE_API_SCOPES_LIST = ['https://www.googleapis.com/auth/spreadsheets']
# --- Конец настроек Google Drive ---

def get_google_sheets_service():
    """Инициализирует и возвращает сервис API Google Sheets."""
    try:
        abs_path = os.path.abspath(GOOGLE_CREDENTIALS_FILE_PATH)
        logger.info(f"--- [DEBUG] Пытаюсь загрузить учетные данные из: {abs_path} ---")
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE_PATH,
            scopes=GOOGLE_API_SCOPES_LIST
        )
        service = build('sheets', 'v4', credentials=creds)
        return service
    except FileNotFoundError:
        logger.error(f"Файл учетных данных Google не найден по пути: {GOOGLE_CREDENTIALS_FILE_PATH}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при инициализации сервиса Google Sheets: {e}")
        raise


def update_moderation_google_sheet(*args, **kwargs): # Убран self из параметров
    """
    Получает данные из ModerationStudioUpload, очищает указанный лист
    в Google Таблице, записывает в него свежие данные и отправляет
    уведомление о результате в Telegram.
    """
    logger.info("Запуск задачи по обновлению Google Таблицы с отчетом модерации.")

    # Определяем параметры для Telegram в одном месте
    group_chat_id = "-1002559221974"
    group_thread_id = "11"

    # 1. Получение данных
    queryset = ModerationStudioUpload.objects.select_related(
        'RenderPhotos__st_request_product__product',
        'RenderPhotos'
    ).filter(IsUploaded=True).order_by('-UploadTimeStart')

    # --- БЛОК ДЛЯ СЛУЧАЯ, КОГДА НЕТ ДАННЫХ ---
    if not queryset.exists():
        logger.info("Данные ModerationStudioUpload с IsUploaded=True не найдены.")
        message_to_send = "ℹ️ Экспорт Uploaded_sku: нет данных для выгрузки. Таблица была очищена."
        try:
            sheets_service = get_google_sheets_service()
            logger.info(f"Очистка листа '{TARGET_SHEET_NAME}'...")
            sheets_service.spreadsheets().values().clear(
                spreadsheetId=TARGET_SPREADSHEET_ID,
                range=TARGET_SHEET_NAME
            ).execute()
            logger.info("Лист успешно очищен.")

            # Попытка отправить уведомление
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=message_to_send,
                message_thread_id=group_thread_id
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке пустого queryset: {e}")
            # Отправляем сообщение об ошибке даже здесь
            error_message = f"‼️ ОШИБКА в задаче 'Экспорт Uploaded_sku' при очистке листа: `{e}`"
            try:
                async_task(
                    'telegram_bot.tasks.send_message_task',
                    chat_id=group_chat_id,
                    text=error_message,
                    message_thread_id=group_thread_id
                )
            except Exception as tg_error:
                logger.error(f"Не удалось отправить уведомление ОБ ОШИБЛЕНИИ в Telegram: {tg_error}")
            # В Dramatiq для повторных попыток просто вызываем исключение
            raise # Dramatiq's retry middleware handles this

        return "Нет данных для генерации отчета. Лист очищен."

    # --- ОСНОВНАЯ ЛОГИКА ---
    serializer = ModerationStudioUploadSerializer(queryset, many=True)
    data_to_export = serializer.data
    headers = ['barcode', 'sku_id', 'category_id', 'UploadTimeStart', 'retouch_link']
    values_to_write = [headers]
    for item in data_to_export:
        row = [item.get(header_key, "") for header_key in headers]
        values_to_write.append(row)

    rows_count = len(values_to_write) - 1
    logger.info(f"Подготовлено {rows_count} строк данных для записи в Google Таблицу.")

    # 3. Работа с Google Sheets API: очистка, запись и уведомления
    try:
        sheets_service = get_google_sheets_service()

        # Шаг 3.1: Очистка листа
        logger.info(f"Очистка листа '{TARGET_SHEET_NAME}'...")
        sheets_service.spreadsheets().values().clear(
            spreadsheetId=TARGET_SPREADSHEET_ID, range=TARGET_SHEET_NAME
        ).execute()
        logger.info("Лист успешно очищен.")

        # Шаг 3.2: Запись новых данных
        logger.info("Запись новых данных...")
        body = {'values': values_to_write}
        update_result = sheets_service.spreadsheets().values().update(
            spreadsheetId=TARGET_SPREADSHEET_ID,
            range=f"{TARGET_SHEET_NAME}!A1",
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()

        # --- Уведомление об УСПЕХЕ ---
        success_message = f"Задача Uploaded\_SKU завершена"
        try:
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=success_message,
                message_thread_id=group_thread_id # можно передать при необходимости
            )
        except Exception as tg_error:
            logger.error(f"Не удалось отправить уведомление об успехе в Telegram: {tg_error}")

        # Возвращаем результат для логов Dramatiq
        final_log_message = f"Google Таблица успешно обновлена. Обработано ячеек: {update_result.get('updatedCells')}."
        logger.info(final_log_message)
        return final_log_message

    except HttpError as error:
        # --- Уведомление об ОШИБКЕ API ---
        error_message = f"ОШИБКА API Google Sheets в задаче Экспорт Uploaded\_sku"
        try:
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=error_message,
                message_thread_id=group_thread_id # можно передать при необходимости
            )
        except Exception as tg_error:
            logger.error(f"Не удалось отправить уведомление ОБ ОШИБЛЕНИИ в Telegram: {tg_error}")

        logger.error(f"Ошибка API Google Sheets: {error.resp.status} - {error._get_reason()}")
        # В Dramatiq middleware Retries будет автоматически обрабатывать повторные попытки
        # если вызовется исключение. Можно настроить max_retries и min_backoff в декораторе
        raise # Dramatiq's retry middleware handles this

    except Exception as e:
        # --- Уведомление о КРИТИЧЕСКОЙ ОШИБКЕ ---
        error_message = f"КРИТИЧЕСКАЯ ОШИБКА в задаче Экспорт Uploaded\_sku"
        try:
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=error_message,
                message_thread_id=group_thread_id
            )
        except Exception as tg_error:
            logger.error(f"Не удалось отправить уведомление ОБ ОШИБЛЕНИИ в Telegram: {tg_error}")

        logger.exception("Полная трассировка неожиданной ошибки:")
        # В Dramatiq middleware Retries будет автоматически обрабатывать повторные попытки
        # если вызовется исключение.
        raise # Dramatiq's retry middleware handles this

#обертка для update_moderation_google_sheet
def update_moderation_google_sheet_custom_timeout():
    """
    Запускает обновление базы продуктов с таймаутом 15 минут.
    Именно эту задачу нужно указывать в Cron-расписании в админке.
    """
    logger.info("Запуск 'update_products_from_excel_on_drive' через обертку с таймаутом 900с")
    async_task(
        'render.tasks.update_moderation_google_sheet',  # Путь к реальной задаче
        timeout=900,   # 15 минут
        retry=1000,    # Повтор через 20 минут, если задача упадет
        attempts=2     # Попробовать 3 раза
    )

###
# --- RENDER ---
###
#Выгрузка для аналитики по конверсии RENDER
# --- Настройки Google Drive определены прямо здесь ---
# ВАЖНО: Укажите правильный путь к вашему файлу credentials.json
GOOGLE_CREDENTIALS_FILE_PATH = 'credentials.json'
credentials_path = 'credentials.json' # 👈 **ОБНОВИТЕ ЭТОТ ПУТЬ**
# ID таблицы бщей папки на Google Drive
RD_TARGET_SPREADSHEET_ID = '1bHJ360rLR-dF-Op7MLvpk_PCNE-88p3fg-GGzj7J0zs'
RD_TARGET_SHEET_NAME = 'data'
# Области доступа для API Google Drive (для создания файлов)
GOOGLE_API_SCOPES_LIST = ['https://www.googleapis.com/auth/spreadsheets']
# --- Конец настроек Google Drive ---

def get_google_sheets_service_rd():
    """Инициализирует и возвращает сервис API Google Sheets."""
    try:
        abs_path = os.path.abspath(GOOGLE_CREDENTIALS_FILE_PATH)
        logger.info(f"--- [DEBUG] Пытаюсь загрузить учетные данные из: {abs_path} ---")
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE_PATH,
            scopes=GOOGLE_API_SCOPES_LIST
        )
        service = build('sheets', 'v4', credentials=creds)
        return service
    except FileNotFoundError:
        logger.error(f"Файл учетных данных Google не найден по пути: {GOOGLE_CREDENTIALS_FILE_PATH}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при инициализации сервиса Google Sheets: {e}")
        raise


def update_moderation_google_sheet_rd(*args, **kwargs): # Убран self из параметров
    """
    Получает данные из ModerationStudioUpload, очищает указанный лист
    в Google Таблице, записывает в него свежие данные и отправляет
    уведомление о результате в Telegram.
    """
    logger.info("Запуск задачи по обновлению Google Таблицы с отчетом модерации.")

    # Определяем параметры для Telegram в одном месте
    group_chat_id = "-1002559221974"
    group_thread_id = "11"

    # 1. Получение данных
    queryset = ModerationUpload.objects.select_related(
        'RenderPhotos__Product',
        'RenderPhotos'
    ).filter(IsUploaded=True).order_by('-UploadTimeStart')

    # --- БЛОК ДЛЯ СЛУЧАЯ, КОГДА НЕТ ДАННЫХ ---
    if not queryset.exists():
        logger.info("Данные ModerationStudioUpload с IsUploaded=True не найдены.")
        message_to_send = "ℹ️ Экспорт Uploaded_Render: нет данных для выгрузки. Таблица была очищена."
        try:
            sheets_service = get_google_sheets_service()
            logger.info(f"Очистка листа '{TARGET_SHEET_NAME}'...")
            sheets_service.spreadsheets().values().clear(
                spreadsheetId=RD_TARGET_SPREADSHEET_ID,
                range=RD_TARGET_SHEET_NAME
            ).execute()
            logger.info("Лист успешно очищен.")

            # Попытка отправить уведомление
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=message_to_send,
                message_thread_id=group_thread_id
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке пустого queryset: {e}")
            # Отправляем сообщение об ошибке даже здесь
            error_message = f"‼️ ОШИБКА в задаче 'Экспорт Uploaded_Render' при очистке листа: `{e}`"
            try:
                async_task(
                    'telegram_bot.tasks.send_message_task',
                    chat_id=group_chat_id,
                    text=error_message,
                    message_thread_id=group_thread_id
                )
            except Exception as tg_error:
                logger.error(f"Не удалось отправить уведомление ОБ ОШИБЛЕНИИ в Telegram: {tg_error}")
            # В Dramatiq для повторных попыток просто вызываем исключение
            raise # Dramatiq's retry middleware handles this

        return "Нет данных для генерации отчета. Лист очищен."

    # --- ОСНОВНАЯ ЛОГИКА ---
    serializer = ModerationUploadSerializer(queryset, many=True)
    data_to_export = serializer.data
    headers = ['barcode', 'sku_id', 'category_id', 'UploadTimeStart', 'retouch_link']
    values_to_write = [headers]
    for item in data_to_export:
        row = [item.get(header_key, "") for header_key in headers]
        values_to_write.append(row)

    rows_count = len(values_to_write) - 1
    logger.info(f"Подготовлено {rows_count} строк данных для записи в Google Таблицу.")

    # 3. Работа с Google Sheets API: очистка, запись и уведомления
    try:
        sheets_service = get_google_sheets_service_rd()

        # Шаг 3.1: Очистка листа
        logger.info(f"Очистка листа '{TARGET_SHEET_NAME}'...")
        sheets_service.spreadsheets().values().clear(
            spreadsheetId=RD_TARGET_SPREADSHEET_ID, range=RD_TARGET_SHEET_NAME
        ).execute()
        logger.info("Лист успешно очищен.")

        # Шаг 3.2: Запись новых данных
        logger.info("Запись новых данных...")
        body = {'values': values_to_write}
        update_result = sheets_service.spreadsheets().values().update(
            spreadsheetId=RD_TARGET_SPREADSHEET_ID,
            range=f"{RD_TARGET_SHEET_NAME}!A1",
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()

        # --- Уведомление об УСПЕХЕ ---
        success_message = f"Задача Uploaded_Render завершена"
        try:
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=success_message,
                message_thread_id=group_thread_id # можно передать при необходимости
            )
        except Exception as tg_error:
            logger.error(f"Не удалось отправить уведомление об успехе в Telegram: {tg_error}")

        # Возвращаем результат для логов Dramatiq
        final_log_message = f"Google Таблица успешно обновлена. Обработано ячеек: {update_result.get('updatedCells')}."
        logger.info(final_log_message)
        return final_log_message

    except HttpError as error:
        # --- Уведомление об ОШИБКЕ API ---
        error_message = f"ОШИБКА API Google Sheets в задаче Экспорт Uploaded_Render"
        try:
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=error_message,
                message_thread_id=group_thread_id # можно передать при необходимости
            )
        except Exception as tg_error:
            logger.error(f"Не удалось отправить уведомление ОБ ОШИБЛЕНИИ в Telegram: {tg_error}")

        logger.error(f"Ошибка API Google Sheets: {error.resp.status} - {error._get_reason()}")
        # В Dramatiq middleware Retries будет автоматически обрабатывать повторные попытки
        # если вызовется исключение. Можно настроить max_retries и min_backoff в декораторе
        raise # Dramatiq's retry middleware handles this

    except Exception as e:
        # --- Уведомление о КРИТИЧЕСКОЙ ОШИБКЕ ---
        error_message = f"КРИТИЧЕСКАЯ ОШИБКА в задаче Экспорт Redner"
        try:
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=error_message,
                message_thread_id=group_thread_id
            )
        except Exception as tg_error:
            logger.error(f"Не удалось отправить уведомление ОБ ОШИБЛЕНИИ в Telegram: {tg_error}")

        logger.exception("Полная трассировка неожиданной ошибки:")
        # В Dramatiq middleware Retries будет автоматически обрабатывать повторные попытки
        # если вызовется исключение.
        raise # Dramatiq's retry middleware handles this
