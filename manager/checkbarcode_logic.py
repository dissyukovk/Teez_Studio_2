from typing import List
from aiogram.utils.markdown import hbold, hcode
from datetime import timedelta
from django.utils import timezone

# Импортируем все необходимые модели
from core.models import (
    Product,
    Nofoto,
    Blocked_Shops,
    Blocked_Barcode,
    OrderProduct,
    RetouchRequestProduct,
    STRequestProduct
)


async def check_barcodes(barcodes: List[str]) -> str:
    """
    Проверяет список штрихкодов по категориям, аналогичным BarcodeCheckView.
    Возвращает отформатированное HTML-сообщение с результатами.
    """
    # 1. Валидация и нормализация
    raw = [bc.strip() for bc in barcodes if bc and bc.strip().isdigit()]
    initial_set = {bc.zfill(13) for bc in raw if len(bc) <= 13}
    if not initial_set:
        return "❗ Нет валидных штрихкодов для проверки."

    barcodes_to_check = initial_set.copy()

    # 2. Инициализация категорий
    has_photo = set()
    in_retouch_queue = set()
    nofoto = set()
    blocked_by_shop = set()
    blocked_by_category = set()
    blocked_by_barcode = set()
    ordered = set()
    onfs = set()
    possible_zero_stock = set()
    
    # 3. Последовательные проверки
    # 3.1 Есть фото
    if barcodes_to_check:
        found = set()
        qs = RetouchRequestProduct.objects.filter(
            st_request_product__product__barcode__in=barcodes_to_check,
            retouch_status__id=2,
            sretouch_status__id=1
        ).values_list('st_request_product__product__barcode', flat=True)
        async for code in qs:
            found.add(code)
        if found:
            has_photo.update(found)
            barcodes_to_check -= found

    # 3.2 В очереди на ретушь
    if barcodes_to_check:
        found = set()
        three_days_ago = timezone.now() - timedelta(hours=20)
        qs = STRequestProduct.objects.filter(
            product__barcode__in=barcodes_to_check,
            photo_status__id=1,
            sphoto_status__id=1,
            senior_check_date__gte=three_days_ago
        ).values_list('product__barcode', flat=True)
        async for code in qs:
            found.add(code)
        if found:
            in_retouch_queue.update(found)
            barcodes_to_check -= found

    # 3.3 Без фото (Nofoto)
    if barcodes_to_check:
        found = set()
        qs = Nofoto.objects.filter(
            product__barcode__in=barcodes_to_check
        ).values_list('product__barcode', flat=True)
        async for code in qs:
            found.add(code)
        if found:
            nofoto.update(found)
            barcodes_to_check -= found

    # 3.4 Блок (магазин)
    if barcodes_to_check:
        found = set()
        shop_ids = {sid async for sid in Blocked_Shops.objects.values_list('shop_id', flat=True)}
        if shop_ids:
            qs = Product.objects.filter(
                barcode__in=barcodes_to_check, 
                seller__in=shop_ids
            ).values_list('barcode', flat=True)
            async for code in qs:
                found.add(code)
            if found:
                blocked_by_shop.update(found)
                barcodes_to_check -= found

    # 3.5 Блок (категория)
    if barcodes_to_check:
        found = set()
        qs = Product.objects.filter(
            barcode__in=barcodes_to_check, 
            category__IsBlocked=True
        ).values_list('barcode', flat=True)
        async for code in qs:
            found.add(code)
        if found:
            blocked_by_category.update(found)
            barcodes_to_check -= found

    # 3.6 Блок (SKU)
    if barcodes_to_check:
        found = set()
        qs = Blocked_Barcode.objects.filter(
            barcode__in=barcodes_to_check
        ).values_list('barcode', flat=True)
        async for code in qs:
            found.add(code)
        if found:
            blocked_by_barcode.update(found)
            barcodes_to_check -= found

    # 3.7 Заказано
    if barcodes_to_check:
        found = set()
        qs = OrderProduct.objects.filter(
            product__barcode__in=barcodes_to_check,
            order__status__id__in=[2, 3]
        ).values_list('product__barcode', flat=True)
        async for code in qs:
            found.add(code)
        if found:
            ordered.update(found)
            barcodes_to_check -= found

    # 3.8 На ФС
    if barcodes_to_check:
        found = set()
        qs = Product.objects.filter(
            barcode__in=barcodes_to_check, 
            move_status__id=3
        ).values_list('barcode', flat=True)
        async for code in qs:
            found.add(code)
        if found:
            onfs.update(found)
            barcodes_to_check -= found

    # 3.9 Возможно нет остатков
    if barcodes_to_check:
        found = set()
        qs = Product.objects.filter(
            barcode__in=barcodes_to_check, 
            in_stock_sum=0
        ).values_list('barcode', flat=True)
        async for code in qs:
            found.add(code)
        if found:
            possible_zero_stock.update(found)
            barcodes_to_check -= found

    # 3.10 Не найдены
    missed = barcodes_to_check

    # 4. Формирование сообщения
    sections = [
        ("✅ Есть фото", has_photo),
        ("⏳ В очереди на ретушь", in_retouch_queue),
        ("🚫 Без фото", nofoto),
        ("🔒 Блок (магазин)", blocked_by_shop),
        ("🔒 Блок (категория)", blocked_by_category),
        ("🔒 Блок (SKU)", blocked_by_barcode),
        ("🛒 Заказано", ordered),
        ("📦 На ФС", onfs),
        ("📉 Возможно нет остатков", possible_zero_stock),
        ("❓ Не найдены", missed),
    ]
    
    lines: List[str] = []
    total_found = len(initial_set) - len(missed)
    lines.append(hbold(f"✅ Проверено: {len(initial_set)}, Найдено: {total_found}"))
    lines.append("")

    for title, bucket in sections:
        if bucket:  # Показываем секцию, только если в ней есть товары
            lines.append(hbold(f"{title} ({len(bucket)})") + ":")
            for code in sorted(bucket):
                lines.append(hcode(code))
            lines.append("")

    return "\n".join(lines).strip()
