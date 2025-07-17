# retoucher/tasks/cleanup_archives.py

import os
import datetime
import logging
import dramatiq # Импортируем dramatiq

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Импортируем вашу конфигурацию брокера для Dramatiq
# Убедитесь, что 'myproject.broker_setup' корректный путь до вашего broker_setup.py
import myproject.broker_setup # Импортируем вашу настройку брокера


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
