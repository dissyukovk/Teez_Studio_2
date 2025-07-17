# manager/product_logic.py
from django.db.models import Q
from aiogram.utils.markdown import hbold, hcode
from core.models import Product, ProductOperation
from django.contrib.auth.models import User, Group

async def update_products_info_by_barcodes(barcodes: list[str], info_text: str) -> dict:
    """
    Обновляет поле 'info' у товаров по списку штрихкодов.
    Возвращает словарь с количеством обновленных и списком ненайденных.
    """
    # --- Обработка штрихкодов с возможными нулями в начале ---
    query_conditions = Q()
    for bc in barcodes:
        query_conditions |= Q(barcode__endswith=bc)

    # Находим существующие товары одним запросом
    products_to_update = Product.objects.filter(query_conditions)

    # Получаем список их реальных штрихкодов для последующей сверки
    found_barcodes_db = {p.barcode async for p in products_to_update}

    # Асинхронно обновляем поле info у всех найденных товаров
    updated_count = await products_to_update.aupdate(info=info_text)

    # --- Определяем ненайденные штрихкоды ---
    # Проверяем каждый штрихкод из пользовательского ввода
    all_user_barcodes_set = set(barcodes)
    found_user_barcodes = {
        user_bc for user_bc in all_user_barcodes_set 
        if any(db_bc.endswith(user_bc) for db_bc in found_barcodes_db)
    }
    missing_barcodes = list(all_user_barcodes_set - found_user_barcodes)

    return {
        "updated_count": updated_count,
        "missing_barcodes": missing_barcodes
    }

async def get_product_operations_by_barcode(barcode: str) -> str:
    """
    Ищет и форматирует историю операций по товару для заданного штрихкода.
    """
    # Используем __endswith для обработки штрихкодов с нулями и без
    operations = ProductOperation.objects.filter(
        product__barcode__endswith=barcode
    ).select_related(
        'product', 'operation_type', 'user'
    ).order_by('-date')

    # Асинхронно получаем все операции
    operations_list = [op async for op in operations[:50]] # Ограничим вывод 50 последними операциями

    if not operations_list:
        return f"Операции для товара со штрихкодом {hcode(barcode)} не найдены."

    # Формируем ответ
    first_op = operations_list[0]
    product_name = first_op.product.name
    real_barcode = first_op.product.barcode

    message_lines = [
        f"Операции для товара: {hbold(product_name)}",
        f"(ШК: {hcode(real_barcode)})",
        "------------------------------------"
    ]

    for op in operations_list:
        date_str = op.date.strftime('%Y-%m-%d %H:%M:%S')
        op_type = op.operation_type.name if op.operation_type else "N/A"
        if op.user:
                # Собираем полное имя из имени и фамилии
                user_name = f"{op.user.first_name} {op.user.last_name}".strip()
                # Если полное имя пустое (не заполнено), используем username как запасной вариант
                if not user_name:
                    user_name = op.user.username
        else:
            user_name = "Система"

        # Безопасно выводим комментарий, экранируя HTML-символы
        comment = op.comment
        comment_str = ""
        if comment:
            # hcode() идеально подходит для вывода любого текста как есть,
            # без форматирования и риска для разметки.
            comment_str = f"\n  └ Комментарий: {hcode(comment)}"

        message_lines.append(f"{hbold(date_str)} - {op_type} - {user_name}{comment_str}")

    return "\n".join(message_lines)
