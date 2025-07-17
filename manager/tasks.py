#manager/tasks.py
from django.db import transaction
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

from core.models import ProductCategory  # поправьте путь, если иначе

logger = logging.getLogger(__name__)

def update_product_categories_from_sheet():
    """
    Обновляет поля ProductCategory по данным из Google Sheet:
    - По столбцу A (ID категории) находит запись.
    - По столбцу H: если там 'Да' — ставит IsReference=True.
    - По столбцу K: устанавливает STRequestType = число из ячейки.
    """
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    SERVICE_ACCOUNT_FILE = 'credentials.json'  # путь к вашему файлу с ключами
    SPREADSHEET_ID = '1NJJn6-Zpm9eLP6v7ys_MW5pWG45KvmfGFA8_5_DoPSo'
    SHEET_NAME = 'Тип съемки'
    RANGE_NAME = f"'{SHEET_NAME}'!A2:K"  # читаем со 2-й строки до колонки K

    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
        rows = result.get('values', [])
    except Exception as e:
        logger.error(f"Не удалось получить данные из Google Sheets: {e}", exc_info=True)
        return

    if not rows:
        logger.info("Лист «Тип съёмки» пустой или диапазон указан неверно.")
        return

    with transaction.atomic():
        for row in rows:
            # Парсим ID категории
            try:
                cat_id = int(row[0])
            except (IndexError, ValueError):
                logger.warning(f"Пропускаем строку с неверным ID: {row}")
                continue

            # Парсим флаг «Есть ли референс» (столбец H, индекс 7)
            is_reference = False
            if len(row) > 7 and str(row[7]).strip().lower() == 'да':
                is_reference = True

            # Парсим тип заявки (столбец K, индекс 10)
            streq_type_id = None
            if len(row) > 10:
                try:
                    streq_type_id = int(row[10])
                except ValueError:
                    logger.warning(f"Невозможно конвертировать STRequestType в число: {row[10]}")

            # Обновляем модель
            try:
                category = ProductCategory.objects.get(id=cat_id)
            except ProductCategory.DoesNotExist:
                logger.warning(f"Категория с id={cat_id} не найдена в БД")
                continue

            updated_fields = []
            if is_reference and not category.IsReference:
                category.IsReference = True
                updated_fields.append('IsReference')
            if streq_type_id and category.STRequestType_id != streq_type_id:
                category.STRequestType_id = streq_type_id
                updated_fields.append('STRequestType')

            if updated_fields:
                category.save(update_fields=updated_fields)
                logger.info(
                    f"Обновлена категория {cat_id}: "
                    f"{', '.join(f'{f}={getattr(category, f)}' for f in updated_fields)}"
                )

    logger.info("Задача update_product_categories_from_sheet завершена.")
