import os
import zipfile
import tempfile
import io
import re
import logging

from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError as GoogleHttpError
from googleapiclient.http import MediaIoBaseDownload

from core.models import User
from retoucher.models import RetouchRequest, RetouchRequestProduct
from tgbot.tgbot import send_custom_message  # твоя утилита для Telegram

logger = logging.getLogger(__name__)

SCOPES_DRIVE_READONLY = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE_ACCOUNT_FILE_PATH = settings.SERVICE_ACCOUNT_FILE


def download_retouch_request_files_task(retouch_request_id, user_id):
    print(f"🎬 Dramatiq Task started: retouch_request_id={retouch_request_id}, user_id={user_id}")
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
            if request_user.profile and request_user.profile.telegram_id:
                send_custom_message(request_user.profile.telegram_id, msg)
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
                    'current': idx,
                    'total': products.count(),
                    'percent': round((idx / products.count()) * 100),
                    'description': f"Обработано: {barcode}"
                })

        final_dir = os.path.join(settings.MEDIA_ROOT, 'retouch_downloads')
        os.makedirs(final_dir, exist_ok=True)
        final_name = f"Исходники_{request_number}.zip"
        final_path = os.path.join(final_dir, final_name)
        os.replace(temp_zip_path, final_path)

        download_url = f"{settings.MEDIA_URL}retouch_downloads/{final_name}"
        frontend_url = f"{settings.API_AND_MEDIA_BASE_URL}{download_url}"

        send_ws_message('complete', {
            'message': f"Архив для заявки {request_number} готов!",
            'download_url': frontend_url
        })

        if request_user.profile and request_user.profile.telegram_id:
            send_custom_message(request_user.profile.telegram_id, f"Готов архив для {request_number}")

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
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
