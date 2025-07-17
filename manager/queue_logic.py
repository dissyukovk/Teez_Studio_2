# manager/queue_logic.py
import asyncio
from django.db.models import Q

from core.models import (
    Order, OrderProduct, STRequest, STRequestProduct, RetouchRequestProduct,
    ProductCategory, Blocked_Shops, Blocked_Barcode, Nofoto
)
from render.models import Render, Product as RenderProduct


async def get_queue_stats_message_async() -> str:
    """
    Асинхронно собирает статистику по всем очередям и возвращает готовое сообщение.
    """
    # --- Словарь задач с добавленной разбивкой ---
    tasks = {
        # --- Созданные заказы ---
        "created_orders": Order.objects.filter(status__id=2).acount(),
        "created_products": OrderProduct.objects.filter(order__status__id=2).acount(),
        "created_products_regular": OrderProduct.objects.filter(order__status__id=2, product__category__STRequestType_id=1).acount(),
        "created_products_clothing": OrderProduct.objects.filter(order__status__id=2, product__category__STRequestType_id=2).acount(),
        "created_products_kgt": OrderProduct.objects.filter(order__status__id=2, product__category__STRequestType_id=3).acount(),

        # --- На сборке ---
        "assembly_orders": Order.objects.filter(status__id=3).acount(),
        "assembly_products": OrderProduct.objects.filter(order__status__id=3).acount(),
        "assembly_products_regular": OrderProduct.objects.filter(order__status__id=3, product__category__STRequestType_id=1).acount(),
        "assembly_products_clothing": OrderProduct.objects.filter(order__status__id=3, product__category__STRequestType_id=2).acount(),
        "assembly_products_kgt": OrderProduct.objects.filter(order__status__id=3, product__category__STRequestType_id=3).acount(),

        # --- Очередь на съемку ---
        "shooting_requests": STRequest.objects.filter(status__id=2).acount(),
        "shooting_products": STRequestProduct.objects.filter(request__status__id=2).acount(),
        "shooting_products_regular": STRequestProduct.objects.filter(request__status__id=2, product__category__STRequestType_id=1).acount(),
        "shooting_products_clothing": STRequestProduct.objects.filter(request__status__id=2, product__category__STRequestType_id=2).acount(),
        "shooting_products_kgt": STRequestProduct.objects.filter(request__status__id=2, product__category__STRequestType_id=3).acount(),

        # --- Остальные очереди (без изменений) ---
        "retouch_queue": STRequestProduct.objects.filter(
            photo_status__id=1, sphoto_status__id=1, OnRetouch=False
        ).acount(),
        "photo_check_requests": STRequestProduct.objects.filter(
            photo_status_id__in=[1, 2, 25]
        ).exclude(
            sphoto_status_id__in=[1, 2, 3]
        ).values('request_id').distinct().acount(),
        "photo_check_products": STRequestProduct.objects.filter(
            photo_status_id__in=[1, 2, 25]
        ).exclude(
            sphoto_status_id__in=[1, 2, 3]
        ).acount(),
        "retouch_check_requests": RetouchRequestProduct.objects.filter(
            Q(retouch_status_id=2) & (Q(sretouch_status_id__isnull=True) | Q(sretouch_status_id=0))
        ).values('retouch_request_id').distinct().acount(),
        "retouch_check_products": RetouchRequestProduct.objects.filter(
            Q(retouch_status_id=2) & (Q(sretouch_status_id__isnull=True) | Q(sretouch_status_id=0))
        ).acount(),
        "render_queue": RenderProduct.objects.filter(
            PhotoModerationStatus="Отклонено",
            IsOnRender=False,
            IsRetouchBlock=False
        ).acount(),
        "render_upload_queue": Render.objects.filter(
            RetouchStatus_id=6, RetouchSeniorStatus_id=1, IsOnUpload=False
        ).acount(),
        "fs_photo_upload_queue": RetouchRequestProduct.objects.filter(
            retouch_status_id=2, sretouch_status_id=1, IsOnUpload=False
        ).acount(),
        "real_shooting_queue": RenderProduct.objects.filter(
            IsOnOrder=False, WMSQuantity__gt=0, PhotoModerationStatus="Отклонено",
            render__CheckResult__id__in=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 50]
        ).exclude(
            ShopID__in=Blocked_Shops.objects.values_list('shop_id', flat=True)
        ).exclude(
            CategoryID__in=ProductCategory.objects.filter(IsBlocked=True).values_list('id', flat=True)
        ).exclude(
            Barcode__in=Blocked_Barcode.objects.values_list('barcode', flat=True)
        ).exclude(
            Barcode__in=Nofoto.objects.values_list('product__barcode', flat=True)
        ).distinct().acount()
    }

    # Запускаем все задачи одновременно
    results = await asyncio.gather(*tasks.values())
    stats = dict(zip(tasks.keys(), results))

    # --- Формирование сообщения ---
    def prepositional_form(count, singular, plural):
        if not isinstance(count, int):
            return plural
        return singular if (count % 10 == 1 and count % 100 != 11) else plural

    # --- Обновленное сообщение с разбивкой ---
    message = (
        "Текущие очереди:\n\n"
        f"📩 *Созданные заказы:* {stats['created_products']} SKU в {stats['created_orders']} {prepositional_form(stats['created_orders'], 'заказе', 'заказах')}:\n"
        f"    Обычные товары - {stats['created_products_regular']}\n"
        f"    Одежда - {stats['created_products_clothing']}\n"
        f"    КГТ - {stats['created_products_kgt']}\n\n"
        
        f"📦 *На сборке:* {stats['assembly_products']} SKU в {stats['assembly_orders']} {prepositional_form(stats['assembly_orders'], 'заказе', 'заказах')}:\n"
        f"    Обычные товары - {stats['assembly_products_regular']}\n"
        f"    Одежда - {stats['assembly_products_clothing']}\n"
        f"    КГТ - {stats['assembly_products_kgt']}\n\n"

        f"📸 *Очередь на съемку на фс:* {stats['shooting_products']} SKU в {stats['shooting_requests']} {prepositional_form(stats['shooting_requests'], 'заявке', 'заявках')}:\n"
        f"    Обычные товары - {stats['shooting_products_regular']}\n"
        f"    Одежда - {stats['shooting_products_clothing']}\n"
        f"    КГТ - {stats['shooting_products_kgt']}\n\n"

        f"🤔 *Очередь на проверку фото:* {stats['photo_check_products']} SKU в {stats['photo_check_requests']} {prepositional_form(stats['photo_check_requests'], 'заявке', 'заявках')}\n\n"
        f"🖌 *Очередь на ретушь:* {stats['retouch_queue']} SKU\n\n"
        f"👀 *Очередь на проверку ретуши:* {stats['retouch_check_products']} SKU в {stats['retouch_check_requests']} {prepositional_form(stats['retouch_check_requests'], 'заявке', 'заявках')}\n\n"
        f"🖼 *Очередь на рендер:* {stats['render_queue']} SKU\n\n"
        f"📤 *Очередь на загрузку фото от ФС:* {stats['fs_photo_upload_queue']} SKU\n\n"
        f"⬆️ *Очередь на загрузку рендеров:* {stats['render_upload_queue']} SKU\n\n"
        f"📸 *Реальная очередь на съемку отклоненных:* {stats['real_shooting_queue']} SKU"
    )
    return message
