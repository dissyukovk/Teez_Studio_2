# manager/stats_logic.py
from datetime import datetime, time
from django.db.models import Sum, Count, Case, When, Q, IntegerField
from django.utils import timezone # <<< Импортируем timezone
from aiogram.utils.markdown import hbold

# ... (импорты ваших моделей остаются такими же) ...
from core.models import (
    OrderProduct, ProductOperation, STRequestProduct, RetouchRequestProduct
)
from render.models import Render, ModerationUpload, ModerationStudioUpload



# vvv Функция теперь async def vvv
async def get_fs_all_stats(date_str: str) -> str:
    """
    Собирает полную статистику фотостудии за указанную дату и возвращает готовое сообщение.
    Теперь работает полностью асинхронно.
    """
    try:
        date_obj = datetime.strptime(date_str, '%d.%m.%Y').date()
    except ValueError:
        return "❌ Неверный формат даты. Используйте: dd.mm.yyyy"

    # Создаем aware (с часовым поясом) datetime объекты
    start_dt = timezone.make_aware(datetime.combine(date_obj, time.min))
    end_dt = timezone.make_aware(datetime.combine(date_obj, time.max))

    # --- Выполняем все агрегации асинхронно с `await` ---

    # 1. Заказано
    ordered_count = await OrderProduct.objects.filter(order__date__range=(start_dt, end_dt)).acount()

    # 2. Операции
    ops_agg = await ProductOperation.objects.filter(date__range=(start_dt, end_dt)).aaggregate(
        accepted=Count('id', filter=Q(operation_type__id=3)),
        sent=Count('id', filter=Q(operation_type__id=4)),
        defective_product=Count('id', filter=Q(operation_type__id__in=[25, 30]))
    )

    # 3. Сфотографировано
    photographed_count = await STRequestProduct.objects.filter(
        request__photo_date__range=(start_dt, end_dt),
        photo_status__id__in=[1, 2, 25], sphoto_status__id=1
    ).acount()

    # 4. Ретушь
    retouch_agg = await RetouchRequestProduct.objects.filter(
        retouch_request__retouch_date__range=(start_dt, end_dt)
    ).aaggregate(
        total_retouched=Count('id', filter=Q(retouch_status__id=2, sretouch_status__id=1)),
        total_defective_shooting=Count('id', filter=Q(retouch_status__id=3, sretouch_status__id=1))
    )
    
    # 5. Рендеры
    renders_agg = await Render.objects.filter(CheckTimeStart__range=(start_dt, end_dt)).aaggregate(
        renders_done=Count('id', filter=Q(RetouchStatus__id=6)),
        renders_rejected=Count('id', filter=Q(RetouchStatus__id=7))
    )

    # 6. Загружено рендеров
    moderation_upload_count = await ModerationUpload.objects.filter(
        UploadTimeStart__range=(start_dt, end_dt), UploadStatus__id=2
    ).acount()

    # 7. Загружено фото от ФС
    moderation_studio_upload_count = await ModerationStudioUpload.objects.filter(
        UploadTimeStart__range=(start_dt, end_dt), UploadStatus__id=2
    ).acount()

    # Собираем все в один словарь (эта часть кода не меняется)
    stats = {
        "Заказано": ordered_count,
        "Принято": ops_agg.get('accepted', 0),
        "Отправлено": ops_agg.get('sent', 0),
        "Брак товара": ops_agg.get('defective_product', 0),
        "Сфотографировано": photographed_count,
        "Отретушировано": retouch_agg.get('total_retouched', 0),
        "Брак по съемке": retouch_agg.get('total_defective_shooting', 0),
        "Сделано рендеров": renders_agg.get('renders_done', 0),
        "Отклонено на рендерах": renders_agg.get('renders_rejected', 0),
        "Загружено рендеров": moderation_upload_count,
        "Загружено фото от фс": moderation_studio_upload_count,
    }
    # ... (весь ваш код форматирования сообщения остается без изменений) ...

    emojis = {
            "Заказано": "📦", "Принято": "📥", "Отправлено": "🚚", "Брак товара": "❌",
            "Сфотографировано": "📸", "Отретушировано": "🎨", "Брак по съемке": "❗",
            "Сделано рендеров": "🖼️", "Отклонено на рендерах": "🚫", "Загружено рендеров": "📤",
            "Загружено фото от фс": "💾",
        }
    display_date = date_obj.strftime('%d.%m.%Y')
    message_lines = [
        f"📊 {hbold(f'Показатели фотостудии за {display_date}:')}",
        "━━━━━━━━━━━━━━━━"
    ]
    
    for key, value in stats.items():
        emoji = emojis.get(key, '❓')
        message_lines.append(f"{emoji} {key}: {hbold(value)}")
    
    message_lines.append("━━━━━━━━━━━━━━━━")

    return "\n".join(message_lines)
