import os
from celery import Celery
from celery.schedules import crontab
import logging

logger = logging.getLogger('celery')
logger.setLevel(logging.DEBUG)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

app = Celery('myproject')

# Настройка из settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматическое обнаружение задач
app.autodiscover_tasks()
app.conf.timezone = 'Asia/Almaty'

# Вставляем расписание задач непосредственно в celery.py
app.conf.beat_schedule = {
##    'check-unverified-photos-every-30-min': {
##        'task': 'auto.tasks.check_unverified_photos',
##        'schedule': 1800.0,  # каждые 30 минут (1800 секунд)
##    },
##    'check-retoucher-queue-every-10-min': {
##        'task': 'auto.tasks.check_retoucher_queue',
##        'schedule': 600.0,  # каждые 10 минут (600 секунд)
##    },
##    'reset-on-work-flag-daily': {
##        'task': 'auto.tasks.reset_on_work_flag',
##        'schedule': crontab(hour=20, minute=5),
##    },
##    'update-strequest-status-every-hour': {
##        'task': 'auto.tasks.update_strequest_status',
##       'schedule': 1200.0,  # каждые 600 секунд 
##    },
##    'birthday-congratulations-daily': {
##        'task': 'auto.tasks.birthday_congratulations',
##        'schedule': crontab(hour=7, minute=53),
##    },
##    'render-autoupdate-daily': {
##       'task': 'render.tasks.update_products_from_drive',
##        'schedule': crontab(hour=7, minute=10), 
##    },
##    'update_renders_and_products_status': {
##        'task': 'render.tasks.update_renders_and_products_status',
##        'schedule': crontab(hour=20, minute=7),
##    },
##    'update_moderation_uploads_status': {
##        'task': 'render.tasks.update_moderation_uploads_status',
##        'schedule': crontab(hour=20, minute=9),
##    },
##    'report_queue_sizes_to_telegram': {
##        'task': 'render.tasks.report_queue_sizes_to_telegram',
##        'schedule': crontab(minute='10', hour='8,16')
##    },
##    'update_priority_for_old_incoming_products': {
##        'task': 'auto.tasks.update_priority_for_old_incoming_products',
##        'schedule': crontab(hour=20, minute=11), 
##    },
##    'update_render_product_retouch_block_status': {
##        'task': 'auto.tasks.update_render_product_retouch_block_status',
##        'schedule': crontab(minute='13', hour='7,20'),
##    },
##    'check_uploads_for_blocked_products': {
##        'task': 'render.tasks.check_uploads_for_blocked_products',
##        'schedule': crontab(minute=0, hour='8,16'),
##    },
##    'update_render_product_is_on_order_status': {
##        'task': 'auto.tasks.update_render_product_is_on_order_status',
##        'schedule': crontab(hour=20, minute=15), 
##    },
##    'update_products_from_excel_on_drive': {
##        'task': 'auto.tasks.update_products_from_excel_on_drive',
##        'schedule': crontab(hour=6, minute=10), 
##    },
##    'update_moderation_google_sheet': {
##        'task': 'render.tasks.update_moderation_google_sheet',
##        'schedule': crontab(hour=20, minute=20),
##    },
##    'write_product_stats_to_google_sheet': {
##        'task': 'auto.tasks.write_product_stats_to_google_sheet',
##        'schedule': crontab(hour=6, minute=55), 
##    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
