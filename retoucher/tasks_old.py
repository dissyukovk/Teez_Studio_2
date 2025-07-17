import pytz
import logging
from datetime import datetime, time, timedelta
from myproject.celery import app
from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.conf import settings # <-- ДОБАВЛЕНО: Импорт settings

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
    ProductCategory,
    APIKeys,
    )
from tgbot.tgbot import send_custom_message

import os
import tempfile
import zipfile
import io # Для работы с байтами в памяти

# Google Drive API imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError as GoogleHttpError # Импорт специфической ошибки Google API
import re # Для get_folder_id_from_url

# Импорты для Channels
from channels.layers import get_channel_layer # <-- НОВЫЙ ИМПОРТ
from asgiref.sync import async_to_sync # <-- НОВЫЙ ИМПОРТ

logger = logging.getLogger(__name__)

SERVICE_ACCOUNT_FILE_PATH = settings.SERVICE_ACCOUNT_FILE
SCOPES_DRIVE_READONLY = ['https://www.googleapis.com/auth/drive.readonly']

def get_folder_id_from_url(url):
    """Извлекает ID папки Google Drive из URL."""
    if not url:
        return None
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None

# Вспомогательная функция для логирования значений строки в Excel (используется в update_products_from_excel_on_drive)
def row_values(row):
    """Вспомогательная функция для логирования значений строки."""
    return [cell.value for cell in row]


@app.task(bind=True, name='retoucher.tasks.download_retouch_request_files_task')
def download_retouch_request_files_task(self, retouch_request_id, user_id):
    """
    Асинхронная задача Celery для скачивания файлов из Google Drive
    и формирования ZIP-архива с использованием Service Account.
    Пользователь будет уведомлен по Telegram и через WebSocket, когда архив будет готов.
    """
    print(f"Task started: retouch_request_id={retouch_request_id}, user_id={user_id}")
    temp_zip_path = None
    channel_layer = get_channel_layer()

    group_name = f'user_task_{user_id}'

    def send_ws_message(message_type, payload):
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'send_task_progress',
                'message': {
                    'type': message_type,
                    'payload': payload
                }
            }
        )

    try:
        retouch_request = RetouchRequest.objects.get(id=retouch_request_id)
        request_user = User.objects.get(id=user_id)

        request_number = retouch_request.RequestNumber

        send_ws_message('status_update', {'stage': 'Инициализация', 'message': 'Начинаю подготовку архива...'})

        # Инициализация Google Drive Service с Service Account Creds
        try:
            creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE_PATH, scopes=SCOPES_DRIVE_READONLY)
            drive_service = build('drive', 'v3', credentials=creds)
            logger.info(f"Google Drive service initialized for task {self.request.id}.")
        except Exception as e:
            error_msg = f"Ошибка инициализации Google Drive Service для заявки {request_number}: {e}"
            logger.error(error_msg, exc_info=True)
            send_ws_message('error', {'message': error_msg})
            if request_user.profile and request_user.profile.telegram_id:
                send_custom_message(request_user.profile.telegram_id, f"Произошла ошибка при подготовке архива для заявки {request_number}: {error_msg}. Пожалуйста, попробуйте позже.")
            raise

        products_to_download = RetouchRequestProduct.objects.filter(
            retouch_request=retouch_request,
            st_request_product__photos_link__isnull=False
        ).select_related(
            'st_request_product__product'
        )

        if not products_to_download.exists():
            message = f"Для заявки {request_number} не найдено продуктов со ссылками на исходники."
            logger.info(message)
            send_ws_message('info', {'message': message})
            if request_user.profile and request_user.profile.telegram_id:
                send_custom_message(request_user.profile.telegram_id, message)
            return {"status": "success", "message": message}

        fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", dir=settings.MEDIA_ROOT)
        os.close(fd)

        downloaded_products_count = 0
        total_products_with_links = products_to_download.count()

        send_ws_message('status_update', {'stage': 'Скачивание', 'message': 'Начинаю скачивание файлов...'})

        # Обертываем внутренний блок скачивания и архивации в try/except/finally
        try: # <-- Начало try блока для операций с ZIP-файлом и скачиванием
            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zipf:
                for product_rrp in products_to_download:
                    folder_url = product_rrp.st_request_product.photos_link
                    barcode = product_rrp.st_request_product.product.barcode

                    send_ws_message('progress', {
                        'current': downloaded_products_count,
                        'total': total_products_with_links,
                        'percent': round((downloaded_products_count / total_products_with_links) * 100) if total_products_with_links > 0 else 0,
                        'description': f"Скачивание папки: {barcode}..."
                    })

                    folder_id = get_folder_id_from_url(folder_url)
                    if not folder_id:
                        logger.warning(f"Некорректная ссылка на папку Google Drive для штрихкода {barcode}: {folder_url}. Пропускаем.")
                        send_ws_message('warning', {'message': f"Пропущена папка '{barcode}': некорректная ссылка."})
                        continue

                    try: # <-- Вложенный try для обработки ошибок конкретного продукта
                        list_response = drive_service.files().list(
                            q=f"'{folder_id}' in parents and trashed=false",
                            fields="files(id,name)",
                            includeItemsFromAllDrives=True,
                            supportsAllDrives=True
                        ).execute()
                        files_data = list_response.get('files', [])

                        if not files_data:
                            logger.info(f"В папке Google Drive для штрихкода {barcode} ({folder_url}) не найдено файлов. Пропускаем.")
                            send_ws_message('warning', {'message': f"Пропущена папка '{barcode}': нет файлов."})
                            continue

                        for file_item in files_data:
                            file_id = file_item['id']
                            file_name = file_item['name']
                            
                            request_file = drive_service.files().get_media(fileId=file_id)
                            
                            file_content_buffer = io.BytesIO()
                            downloader = MediaIoBaseDownload(file_content_buffer, request_file)
                            done = False
                            while not done:
                                status_progress, done = downloader.next_chunk()

                            file_content_buffer.seek(0)
                            
                            zipf.writestr(f"{barcode}/{file_name}", file_content_buffer.getvalue())
                            logger.info(f"Файл '{file_name}' для штрихкода '{barcode}' успешно добавлен в архив.")
                        
                        downloaded_products_count += 1
                        self.update_state(
                            state='PROGRESS',
                            meta={
                                'current_products': downloaded_products_count,
                                'total_products': total_products_with_links,
                                'percent_complete': round((downloaded_products_count / total_products_with_links) * 100) if total_products_with_links > 0 else 0,
                                'description': f"Скачано {downloaded_products_count} из {total_products_with_links} папок."
                            }
                        )

                    except GoogleHttpError as google_err:
                        logger.error(f"Ошибка Google Drive API для штрихкода {barcode}: {google_err.resp.status} - {google_err.content.decode()}", exc_info=True)
                        send_ws_message('error', {'message': f"Ошибка Google Drive для '{barcode}': {google_err.resp.status}."})
                    except Exception as e:
                        logger.error(f"Общая ошибка при обработке штрихкода {barcode}: {e}", exc_info=True)
                        send_ws_message('error', {'message': f"Неизвестная ошибка для '{barcode}': {e}."})
                        continue # Продолжить для следующего продукта
            
            # После успешного создания ZIP-архива
            download_dir = os.path.join(settings.MEDIA_ROOT, 'retouch_downloads')
            os.makedirs(download_dir, exist_ok=True)

            final_zip_filename = f"Исходники_{request_number}.zip"
            final_zip_path = os.path.join(download_dir, final_zip_filename)

            os.replace(temp_zip_path, final_zip_path)
            
            download_url = f"{settings.MEDIA_URL}retouch_downloads/{final_zip_filename}"

            logger.info(f"Архив для заявки {request_number} успешно создан: {final_zip_path}. URL: {download_url}")
            
            base_url = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000')
            full_download_url = f"{base_url}{download_url}"

            # Отправляем финальное сообщение на фронтенд через WebSocket
            send_ws_message('complete', {
                'message': f"Архив для заявки {request_number} готов!",
                'download_url': full_download_url
            })
            
            # Отправляем уведомление пользователю с ссылкой на скачивание
            if request_user.profile and request_user.profile.telegram_id:
                message_text = (
                    f"Архив с исходниками для заявки {request_number} готов! "
                    f"Скачать: {full_download_url}"
                )
                send_custom_message(request_user.profile.telegram_id, message_text)
            else:
                logger.warning(f"Пользователь {request_user.username} не имеет Telegram ID для уведомления.")

            return {"status": "success", "download_url": download_url, "message": "Архив готов!"}

        except Exception as e: # <-- Этот except ловит ошибки из блока with zipfile.ZipFile
            error_msg = f"Ошибка при создании/заполнении ZIP-архива для заявки {request_number}: {e}"
            logger.error(error_msg, exc_info=True)
            raise # Перевыбрасываем, чтобы поймал внешний try/except

    except Exception as e: # <-- Внешний try блок, который ловит любые критические ошибки в задаче
        error_msg = f"Критическая ошибка в задаче скачивания для заявки {retouch_request_id} (пользователь {user_id}): {e}"
        logger.error(error_msg, exc_info=True)
        send_ws_message('error', {'message': error_msg})
        
        try:
            request_user = User.objects.get(id=user_id)
            if request_user.profile and request_user.profile.telegram_id:
                try:
                    retouch_request_for_msg = RetouchRequest.objects.get(id=retouch_request_id)
                except RetouchRequest.DoesNotExist:
                    retouch_request_for_msg = None
                
                req_num_for_msg = retouch_request_for_msg.RequestNumber if retouch_request_for_msg else f"ID {retouch_request_id}"
                error_notification_message = (
                    f"Произошла ошибка при подготовке архива для заявки {req_num_for_msg}: {e}. "
                    f"Пожалуйста, свяжитесь с администратором."
                )
                send_custom_message(request_user.profile.telegram_id, error_notification_message)
        except User.DoesNotExist:
            logger.error(f"Не удалось найти пользователя {user_id} для отправки уведомления об ошибке.")
        except Exception as notify_e:
            logger.error(f"Ошибка при попытке уведомить пользователя об ошибке: {notify_e}", exc_info=True)

        raise # Celery пометит задачу как Failed
    finally:
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
                logger.info(f"Временный ZIP-файл {temp_zip_path} удален.")
            except Exception as e:
                logger.error(f"Не удалось удалить временный ZIP-файл {temp_zip_path}: {e}")
