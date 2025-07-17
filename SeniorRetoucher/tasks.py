# SeniorRetoucher/tasks.py
import logging
import re
from datetime import timedelta

from aiogram.utils.markdown import hbold, hcode
from django.conf import settings
from django.utils import timezone
from django_q.tasks import async_task
from django.db import transaction
from django.db.models import Max
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Импортируем нужные модели из core приложения
# Убедитесь, что путь импорта соответствует вашей структуре проекта
from core.models import RetouchRequestProduct, STRequestProduct, RetouchRequest

# Настраиваем логирование
logger = logging.getLogger(__name__)


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


# --- ИСПРАВЛЕННАЯ ВЕРСИЯ ЭТОЙ ЗАДАЧИ ---
def check_retoucher_folders():
    """
    Проверяет папки ретушеров на корректность ссылок и количество файлов.
    Собирает списки проблемных товаров и отправляет отчет в Telegram.
    """
    logger.info("Запуск задачи проверки папок ретушеров...")

    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
    products_to_check = RetouchRequestProduct.objects.filter(
        retouch_status_id=2,
        sretouch_status_id=1,
        retouch_end_date__gte=thirty_minutes_ago
    ).select_related('st_request_product__product')

    if not products_to_check:
        logger.info("Нет продуктов от ретушеров для проверки. Задача завершена.")
        return

    logger.info(f"Найдено {len(products_to_check)} продуктов для проверки.")

    link_error_list = []
    too_few_files_list = []

    # Создаем подключение к Google API ОДИН РАЗ перед циклом
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
        if not item.st_request_product or not item.st_request_product.product:
            continue
        
        barcode = item.st_request_product.product.barcode
        retouch_link = item.retouch_link

        # --- ИСПРАВЛЕНИЕ ЗДЕСЬ: Передаем 'google_service' как первый аргумент ---
        file_count = _get_google_drive_file_count(google_service, retouch_link)

        if file_count is None:
            link_error_list.append(hcode(barcode))
        elif file_count < 3:
            too_few_files_list.append(f"{hcode(barcode)} - {retouch_link or 'Ссылка отсутствует'}")

    # ... (остальная часть функции для отправки сообщения остается без изменений) ...
    if link_error_list or too_few_files_list:
        message_parts = [hbold("🚨 Результаты проверки папок ретушеров 🚨\n")]

        if link_error_list:
            message_parts.append(hbold("Ошибка в ссылке (недоступна или неверный формат):"))
            message_parts.extend(link_error_list)
            message_parts.append("")

        if too_few_files_list:
            message_parts.append(hbold("Слишком мало файлов (< 4):"))
            message_parts.extend(too_few_files_list)

        message_text = "\n".join(message_parts)
        
        logger.info(f"Отправка отчета в чат {TARGET_CHAT_ID} (тема {MESSAGE_THREAD_ID})...")
        async_task(
            'telegram_bot.tasks.send_message_task',
            chat_id=TARGET_CHAT_ID,
            text=message_text,
            message_thread_id=MESSAGE_THREAD_ID,
            parse_mode='HTML',
            disable_web_page_preview=True 
        )
    else:
        logger.info("Проблемных товаров от ретушеров не найдено.")

    logger.info("Задача проверки папок ретушеров завершена.")


#Автосоздание заявок на ретушь
def schedule_auto_retouch_requests():
    """
    Периодическая задача для автоматического создания заявок на ретушь.
    Запускается по расписанию через Django-Q.
    Создает заявки только для количества продуктов, кратного 10.
    """
    logger.info("Запуск задачи автоматического создания заявок на ретушь...")

    # 1. Находим все продукты, готовые к ретуши
    ready_products_qs = STRequestProduct.objects.filter(
        photo_status_id=1,
        sphoto_status_id=1,
        OnRetouch=False
    ).order_by('product__income_date')

    product_count = ready_products_qs.count()

    # 2. Проверяем, есть ли хотя бы 10 продуктов для создания заявки
    if product_count < 10:
        logger.info(f"Найдено {product_count} продуктов для ретуши. Требуется 10 или больше. Завершаю работу.")
        return f"Найдено {product_count} продуктов, работа не требуется."

    # --- НОВАЯ ЛОГИКА ---
    # 3. Определяем, сколько продуктов будем обрабатывать (округляем вниз до 10)
    products_to_process_count = (product_count // 10) * 10
    logger.info(f"Всего найдено {product_count} продуктов. Будет обработано: {products_to_process_count}.")
    
    # 4. Получаем ID только тех продуктов, которые будем обрабатывать
    product_ids_to_process = list(ready_products_qs.values_list('id', flat=True)[:products_to_process_count])
    # --- КОНЕЦ НОВОЙ ЛОГИКИ ---
    
    created_requests_count = 0
    
    # 5. Обрабатываем продукты пачками по 10. Цикл теперь будет работать только с полными пачками.
    for i in range(0, len(product_ids_to_process), 10):
        chunk_ids = product_ids_to_process[i:i+10]

        try:
            with transaction.atomic():
                # Генерируем новый номер заявки
                last_request_number = RetouchRequest.objects.aggregate(max_number=Max('RequestNumber'))['max_number']
                new_request_number = (last_request_number or 0) + 1
                
                logger.info(f"Создание заявки #{new_request_number} для {len(chunk_ids)} продуктов.")

                # Создаем RetouchRequest
                new_request = RetouchRequest.objects.create(
                    RequestNumber=new_request_number,
                    retoucher=None,
                    status_id=1,
                    creation_date=timezone.now()
                )

                products_in_chunk = STRequestProduct.objects.filter(id__in=chunk_ids)

                # Создаем связи и обновляем статус
                RetouchRequestProduct.objects.bulk_create([
                    RetouchRequestProduct(retouch_request=new_request, st_request_product=st_product)
                    for st_product in products_in_chunk
                ])
                products_in_chunk.update(OnRetouch=True)
                
                # Запускаем фоновую загрузку файлов
                task_id = async_task(
                    'retoucher.tasks.download_retouch_request_files_task',
                    retouch_request_id=new_request.id,
                    user_id=None
                )
                
                new_request.download_task_id = task_id
                new_request.download_started_at = timezone.now()
                new_request.save(update_fields=['download_task_id', 'download_started_at'])
                
                logger.info(f"Успешно создана заявка {new_request.id} и запущена задача на загрузку {task_id}.")
                created_requests_count += 1

        except Exception as e:
            logger.error(f"Ошибка при создании заявки для пачки продуктов (индекс {i}). Ошибка: {e}", exc_info=True)

    # 6. Отправляем итоговое сообщение в Telegram
    if created_requests_count > 0:
        logger.info(f"Успешно создано {created_requests_count} новых заявок на ретушь.")
        
        message = f"Создано заявок на ретушь автоматически - {created_requests_count}. Загрузка завершена"
        chat_id = -1002559221974
        thread_id = 11

        try:
            async_task(
                'telegram_bot.tasks.send_message_task',
                chat_id=chat_id,
                text=message,
                message_thread_id=thread_id
            )
            logger.info(f"Отправлено итоговое уведомление в Telegram чат {chat_id}, тред {thread_id}.")
        except Exception as e:
             logger.error(f"Не удалось отправить итоговое уведомление в Telegram. Ошибка: {e}", exc_info=True)
        
        return f"Успешно создано {created_requests_count} заявок."
    
    return "Новых заявок не создано."
