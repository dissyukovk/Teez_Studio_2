#retoucher/tasks.py
import os
import zipfile
import tempfile
import io
import re
import logging
import datetime
from django.conf import settings
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django_q.tasks import async_task
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError as GoogleHttpError
from googleapiclient.http import MediaIoBaseDownload

from core.models import User
from retoucher.models import RetouchRequest, RetouchRequestProduct
from aiogram.utils.markdown import hlink

logger = logging.getLogger(__name__)

SCOPES_DRIVE_READONLY = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE_ACCOUNT_FILE_PATH = settings.SERVICE_ACCOUNT_FILE


def download_retouch_request_files_task(retouch_request_id, user_id=None):
    """
    Загружает файлы для заявки на ретушь.
    user_id является необязательным. Если он не указан, WebSocket и Telegram
    уведомления для конкретного пользователя не отправляются.
    """
    temp_zip_path = None
    
    # --- БЛОК 1: Безопасная обработка user_id ---
    # Этот блок выполняется всегда и корректно обрабатывает как наличие,
    # так и отсутствие user_id.
    channel_layer = None
    group_name = None
    request_user = None # По умолчанию пользователя нет
    
    if user_id:
        # Если user_id передан, настраиваем уведомления
        channel_layer = get_channel_layer()
        group_name = f'user_task_{user_id}'
        try:
            # И пытаемся найти пользователя
            request_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            # Если пользователь не найден, просто сбрасываем user_id, чтобы не было ошибок
            logger.warning(f"User for notification (id={user_id}) not found in download task.")
            user_id = None

    def send_ws_message(message_type, payload):
        # Эта функция отправит сообщение, только если user_id был найден
        if user_id and channel_layer:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {'type': 'send_task_progress', 'message': {'type': message_type, 'payload': payload}}
            )

    try:
        # --- БЛОК 2: Основная логика ---
        # Получаем заявку. Это действие не зависит от пользователя.
        retouch_request = RetouchRequest.objects.get(id=retouch_request_id)
        request_number = retouch_request.RequestNumber

        # ❌ ПРОБЛЕМНАЯ СТРОКА УДАЛЕНА ОТСЮДА ❌
        # Здесь больше нет `request_user = User.objects.get(id=user_id)`

        send_ws_message('status_update', {'stage': 'Инициализация', 'message': 'Начинаю подготовку архива...'})

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE_PATH, scopes=SCOPES_DRIVE_READONLY)
        drive_service = build('drive', 'v3', credentials=creds)

        products = RetouchRequestProduct.objects.filter(
            retouch_request=retouch_request,
            st_request_product__photos_link__isnull=False
        ).select_related('st_request_product__product')

        if not products.exists():
            msg = f"Нет продуктов со ссылками у заявки {request_number}"
            send_ws_message('info', {'message': msg})
            # Эта проверка уже использует `request_user` из Блока 1, что безопасно
            if request_user and request_user.profile and request_user.profile.telegram_id:
                async_task(
                    'telegram_bot.tasks.send_message_task',
                    chat_id=request_user.profile.telegram_id,
                    text=msg
                )
            return

        fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", dir=settings.MEDIA_ROOT)
        os.close(fd)

        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, p in enumerate(products, start=1):
                folder_id = get_folder_id_from_url(p.st_request_product.photos_link)
                barcode = p.st_request_product.product.barcode

                if not folder_id:
                    continue

                try:
                    response = drive_service.files().list(
                        q=f"'{folder_id}' in parents and trashed=false",
                        fields="files(id,name)",
                        includeItemsFromAllDrives=True,
                        supportsAllDrives=True
                    ).execute()

                    for f in response.get('files', []):
                        file_id, file_name = f['id'], f['name']
                        request = drive_service.files().get_media(fileId=file_id)
                        buf = io.BytesIO()
                        downloader = MediaIoBaseDownload(buf, request)
                        done = False
                        while not done:
                            _, done = downloader.next_chunk()
                        buf.seek(0)
                        zipf.writestr(f"{barcode}/{file_name}", buf.read())

                except Exception as e:
                    logger.warning(f"Ошибка при обработке {barcode}: {e}")

                send_ws_message('progress', {
                    'current': idx, 'total': products.count(), 'percent': round((idx / products.count()) * 100),
                    'description': f"Обработано: {barcode}"
                })

        final_dir = os.path.join(settings.MEDIA_ROOT, 'retouch_downloads')
        os.makedirs(final_dir, exist_ok=True)
        final_name = f"Исходники_{request_number}.zip"
        final_path = os.path.join(final_dir, final_name)
        os.replace(temp_zip_path, final_path)

        # Эта проверка также использует `request_user` из Блока 1
        if user_id and request_user:
            download_url = f"{settings.MEDIA_URL}retouch_downloads/{final_name}"
            frontend_url = f"{settings.API_AND_MEDIA_BASE_URL}{download_url}"

            send_ws_message('complete', {
                'message': f"Архив для заявки {request_number} готов!",
                'download_url': frontend_url
            })
            message = f"Готов архив для {request_number} \n {frontend_url}"
            if request_user.profile and request_user.profile.telegram_id:
                async_task(
                    'telegram_bot.tasks.send_message_task', 
                    chat_id=request_user.profile.telegram_id,
                    text=message
                )

        ret_req = RetouchRequest.objects.get(id=retouch_request_id)
        ret_req.download_completed_at = timezone.now()
        ret_req.save(update_fields=['download_completed_at'])

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        try:
            RetouchRequest.objects.filter(id=retouch_request_id).update(download_error=str(e))
        except:
            pass
        send_ws_message('error', {'message': f"Ошибка: {e}"})

    finally:
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.remove(temp_zip_path)
            except:
                pass

def get_folder_id_from_url(url):
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', url or '')
    return match.group(1) if match else None

def cleanup_old_retouch_archives(days_to_keep=1):
    """
    Dramatiq task to delete old retouch request archives from the media directory.
    By default, deletes archives older than 1 day.
    """
    cleanup_threshold = timezone.now() - datetime.timedelta(days=days_to_keep)

    archive_dir = os.path.join(settings.MEDIA_ROOT, 'retouch_downloads')
    logger.info(f"Starting cleanup of old archives in: {archive_dir}. Deleting files older than {days_to_keep} day(s).")

    if not os.path.exists(archive_dir):
        logger.warning(f"Directory '{archive_dir}' does not exist. Skipping cleanup.")
        return

    deleted_count = 0
    for filename in os.listdir(archive_dir):
        file_path = os.path.join(archive_dir, filename)
        if os.path.isfile(file_path):
            try:
                # Получаем время последнего изменения файла.
                # Для корректного сравнения с timezone.now(), делаем его aware.
                # timezone.get_current_timezone() вернет 'Asia/Almaty' из ваших настроек.
                file_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.get_current_timezone())

                if file_modified_time < cleanup_threshold:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted: {filename} (last modified: {file_modified_time.strftime('%Y-%m-%d %H:%M:%S')})")
            except Exception as e:
                logger.error(f"Error deleting file {filename}: {e}", exc_info=True)

    logger.info(f"Cleanup finished. {deleted_count} old archives deleted.")
