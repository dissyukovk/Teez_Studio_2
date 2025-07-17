# telegram_bot/keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def get_base_keyboard_builder() -> ReplyKeyboardBuilder:
    """
    Возвращает "строитель" (builder) с базовым набором кнопок, доступных всем.
    """
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="🔀 Очереди")
    )
    builder.row(
        KeyboardButton(text="✅ Готовые фото"),
        KeyboardButton(text="🔑 Привязать аккаунт")
    )
    builder.row(
        KeyboardButton(text="❔ Операции"),
        KeyboardButton(text="🔍 Проверить ШК")
    )
    return builder

# --- Функции для добавления кнопок по ролям ---

def add_manager_buttons(builder: ReplyKeyboardBuilder) -> ReplyKeyboardBuilder:
    """Добавляет кнопки менеджера к существующему строителю."""
    builder.row(KeyboardButton(text="⚠️ Обновить инфо"))
    return builder

def add_stockman_buttons(builder: ReplyKeyboardBuilder) -> ReplyKeyboardBuilder:
    """Добавляет кнопки товароведа к существующему строителю."""
    # Добавляем кнопки в 2 колонки
    return builder

# --- Финальные функции, которые мы будем вызывать ---

def get_default_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает финальную клавиатуру для гостя."""
    builder = get_base_keyboard_builder()
    return builder.as_markup(resize_keyboard=True)

def get_dynamic_keyboard_for_user(user_groups: list) -> ReplyKeyboardMarkup:
    """
    Создает и возвращает динамическую клавиатуру на основе списка групп пользователя.
    """
    builder = get_base_keyboard_builder()

    if 'Менеджер' in user_groups:
        builder = add_manager_buttons(builder)
    
    if 'Товаровед' in user_groups:
        builder = add_stockman_buttons(builder)
    
    # Сюда можно добавлять 'if' для других ролей...

    return builder.as_markup(resize_keyboard=True)
