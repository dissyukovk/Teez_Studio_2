# photographer/photo_logic.py
from django.db.models import Q
from aiogram.utils.markdown import hlink, hcode

from core.models import RetouchRequestProduct

async def get_ready_photos_by_barcodes(barcodes: list[str]) -> str:
    """
    Ищет готовые фото по списку штрихкодов и возвращает отформатированное сообщение.
    Решает проблему с ведущими нулями в штрихкодах.
    """
    if not barcodes:
        return "Вы не прислали штрихкоды."

    # --- Решение проблемы с нулями ---
    # Мы будем искать по каждому штрихкоду, проверяя, не является ли он окончанием
    # записи в базе данных. Это найдет и '123' в '000123'.
    # Создаем список Q-объектов для сложного поиска.
    query_conditions = Q()
    for bc in barcodes:
        # Ищем точное совпадение ИЛИ совпадение по окончанию строки
        query_conditions |= Q(st_request_product__product__barcode__endswith=bc)

    # Выполняем один запрос к БД
    queryset = RetouchRequestProduct.objects.filter(
        query_conditions,
        retouch_status_id=2,
        sretouch_status_id=1
    ).select_related('st_request_product__product').distinct()
    # .aresult() - это как .all(), но для асинхронного выполнения
    found_products = [item async for item in queryset]

    found_links = {}
    # Сохраняем найденные ссылки и реальные штрихкоды из базы
    for product in found_products:
        real_barcode = product.st_request_product.product.barcode
        link = product.retouch_link or "нет ссылки"
        found_links[real_barcode] = link

    # --- Формируем ответ ---
    reply_lines = []
    found_barcodes_from_db = set(found_links.keys())
    # Проверяем каждый штрихкод из пользовательского ввода
    processed_user_barcodes = set()

    for user_barcode in barcodes:
        if user_barcode in processed_user_barcodes:
            continue # Пропускаем дубликаты из пользовательского ввода

        # Ищем совпадение по окончанию строки в найденных штрихкодах
        matched_barcode = next((db_bc for db_bc in found_barcodes_from_db if db_bc.endswith(user_barcode)), None)

        if matched_barcode:
            link = found_links[matched_barcode]
            # Используем hlink для безопасного создания ссылок
            reply_lines.append(f"{hcode(matched_barcode)} - {hlink('Ссылка', link)}")

        processed_user_barcodes.add(user_barcode)

    # Определяем ненайденные штрихкоды
    all_user_barcodes_set = set(barcodes)
    found_user_barcodes = {user_bc for user_bc in all_user_barcodes_set if any(db_bc.endswith(user_bc) for db_bc in found_barcodes_from_db)}
    not_found_barcodes = all_user_barcodes_set - found_user_barcodes

    if not_found_barcodes:
        reply_lines.append("\n" + "Не найдены штрихкоды: " + ", ".join(not_found_barcodes))

    if not reply_lines:
        return "По вашим штрихкодам ничего не найдено."

    return "\n".join(reply_lines)
