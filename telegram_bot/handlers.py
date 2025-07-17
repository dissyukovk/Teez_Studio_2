# telegram_bot/handlers.py
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta

# Импортируем наши обновленные клавиатуры, состояния и логику
from . import keyboards
from .states import (
    StatsState, ReadyPhotosState, AuthState, UpdateInfoState, OperationsState, CheckBarcodesState
    )

from .auth_logic import check_user_credentials, update_user_telegram_profile
from manager.stats_logic import get_fs_all_stats
from manager.queue_logic import get_queue_stats_message_async
from manager.photo_logic import get_ready_photos_by_barcodes
from manager.product_logic import update_products_info_by_barcodes
from manager.product_logic import get_product_operations_by_barcode
from manager.checkbarcode_logic import check_barcodes 
from core.models import UserProfile
from telegram_bot.bot_instance import bot

# Создаем Router
router = Router()


# --- Обработчик команды /start (теперь с поддержкой нескольких ролей) ---
@router.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext) -> None:
    """
    Этот обработчик срабатывает на команду /start, определяет ВСЕ роли
    пользователя и строит для него составную клавиатуру.
    """
    await state.clear()

    try:
        user_profile = await UserProfile.objects.select_related('user').aget(telegram_id=str(message.from_user.id))
        user = user_profile.user
        user_groups = [group.name async for group in user.groups.all()]

        if not user_groups:
            # Пользователь есть, но без ролей
            response_text = f"Здравствуйте, {user.first_name}! У вас нет специфической роли."
            reply_markup = keyboards.get_default_keyboard()
        else:
            # Пользователь с одной или несколькими ролями
            response_text = f"Здравствуйте, {user.first_name}!"
            # Вызываем нашу новую динамическую функцию
            reply_markup = keyboards.get_dynamic_keyboard_for_user(user_groups)

    except UserProfile.DoesNotExist:
        # Неавторизованный пользователь
        response_text = "Здравствуйте! Вы можете использовать общие команды или привязать аккаунт."
        reply_markup = keyboards.get_default_keyboard()

    await message.answer(response_text, reply_markup=reply_markup)


# --- Обработчик кнопки "Статистика" (доступен всем, логика без изменений) ---
@router.message(Command("stats"))
@router.message(F.text == "📊 Статистика")
async def process_stats_button(message: types.Message, state: FSMContext):
    # Создаем inline-кнопки
    stats_keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Сегодня", callback_data="stats_period_today"),
            types.InlineKeyboardButton(text="Вчера", callback_data="stats_period_yesterday")
        ]
    ])
    
    # Устанавливаем состояние ожидания на случай, если пользователь введет дату вручную
    await state.set_state(StatsState.waiting_for_date)
    
    # Отправляем сообщение с кнопками
    sent_message = await message.answer(
        "Выберите период или введите дату вручную в формате *ДД.ММ.ГГГГ*.",
        reply_markup=stats_keyboard,
        parse_mode="Markdown"
    )
    # Сохраняем ID сообщения, чтобы потом его отредактировать
    await state.update_data(message_to_edit=sent_message.message_id)


# --- НОВЫЙ Обработчик нажатий на кнопки "Сегодня" / "Вчера" ---
@router.callback_query(F.data.startswith("stats_period_"))
async def process_stats_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer() # "убираем часики"
    period = callback.data.split("_")[-1]

    if period == "today":
        date_obj = datetime.now()
    elif period == "yesterday":
        date_obj = datetime.now() - timedelta(days=1)
    else:
        await callback.message.edit_text("Неизвестный период.")
        await state.clear()
        return

    date_str = date_obj.strftime('%d.%m.%Y')

    # Показываем, что мы работаем
    await callback.message.edit_text(f"🔍 Собираю статистику за {date_str}, подождите...")

    stats_message = await get_fs_all_stats(date_str)
    await callback.message.edit_text(stats_message)
    await state.clear()


# --- ОБНОВЛЕННЫЙ Обработчик ручного ввода даты ---
@router.message(StatsState.waiting_for_date)
async def process_date_for_stats(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    message_id_to_edit = user_data.get("message_to_edit")

    # Удаляем сообщение пользователя с датой, чтобы не мусорить в чате
    await message.delete()

    date_input = message.text.strip()
    
    # Показываем, что мы работаем, редактируя исходное сообщение
    if message_id_to_edit:
        await bot.edit_message_text(f"🔍 Собираю статистику за {date_input}, подождите...", chat_id=message.chat.id, message_id=message_id_to_edit)

    stats_message = await get_fs_all_stats(date_input)
    
    # Редактируем исходное сообщение с результатом
    if message_id_to_edit:
        await bot.edit_message_text(stats_message, chat_id=message.chat.id, message_id=message_id_to_edit)
    else: # Если по какой-то причине ID не сохранился, просто отправляем новое
        await message.answer(stats_message)

    if "❌" not in stats_message:
        await state.clear()


# --- Обработчик кнопки Очереди ---
@router.message(Command("queue"))
@router.message(F.text == "🔀 Очереди")
async def process_queues_button(message: types.Message):
    # Отправляем временное сообщение
    from manager.queue_logic import get_queue_stats_message_async
    temp_message = await message.answer("🔍 Собираю статистику по очередям, пожалуйста, подождите...")

    try:
        # Вызываем нашу новую асинхронную функцию
        stats_message = await get_queue_stats_message_async()
        # Редактируем временное сообщение, заменяя его на результат
        await temp_message.edit_text(stats_message, parse_mode="Markdown")
    except Exception as e:
        # В случае любой ошибки сообщаем пользователю
        await temp_message.edit_text("❌ Произошла ошибка при сборе статистики.")
        # Также логируем ошибку для себя
        print(f"Error in get_queue_stats_message_async: {e}")


# --- Обработчик кнокпи Готовые фото ---
@router.message(Command("readyphotos"))
@router.message(F.text == "✅ Готовые фото")
async def process_ready_photos_button(message: types.Message, state: FSMContext):
    from manager.photo_logic import get_ready_photos_by_barcodes
    await state.set_state(ReadyPhotosState.waiting_for_barcodes)
    await message.answer(
        "Пришлите штрихкоды товаров для поиска.\n"
        "Каждый штрихкод на новой строчке."
    )

# --- Обработчик состояния ожидания штрихкодов ---
@router.message(ReadyPhotosState.waiting_for_barcodes)
async def process_barcodes_for_photos(message: types.Message, state: FSMContext):
    from manager.photo_logic import get_ready_photos_by_barcodes
    # Отправляем временное сообщение, т.к. поиск может занять время
    temp_message = await message.answer("🔍 Идет поиск по базе...")

    # Извлекаем штрихкоды из сообщения, убирая пустые строки
    barcodes = [line.strip() for line in message.text.split('\n') if line.strip()]

    if not barcodes:
        await temp_message.edit_text("Вы не прислали штрихкоды. Попробуйте еще раз.")
        # Остаемся в том же состоянии, чтобы пользователь мог повторить ввод
        return

    # Вызываем нашу функцию для поиска и формирования ответа
    reply_message = await get_ready_photos_by_barcodes(barcodes)

    # Редактируем временное сообщение, заменяя его на результат
    await temp_message.edit_text(reply_message)

    # Выходим из состояния
    await state.clear()



# --- Приязать аккаунт ---

# --- Обработчик кнопки "Привязать аккаунт" ---
@router.message(Command("addtelegramid"))
@router.message(F.text == "🔑 Привязать аккаунт")
async def process_attach_account_button(message: types.Message, state: FSMContext):
    # Эта операция должна проходить только в личных сообщениях
    if message.chat.type != "private":
        await message.answer("Привязать аккаунт можно только в личном чате с ботом.")
        return

    from core.models import UserProfile
    try:
        # Проверяем, есть ли уже профиль с таким ID
        profile = await UserProfile.objects.select_related('user').aget(telegram_id=str(message.from_user.id))
        # Если есть, спрашиваем подтверждение на перезапись
        await state.set_state(AuthState.waiting_for_confirmation)

        # Создаем inline-кнопки для подтверждения
        confirmation_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Да, привязать к новому", callback_data="auth_confirm_yes")],
            [types.InlineKeyboardButton(text="Нет, отмена", callback_data="auth_confirm_no")]
        ])
        await message.answer(
            f"Ваш Telegram уже привязан к пользователю *{profile.user.username}*.\n"
            "Хотите привязать его к другому аккаунту?",
            reply_markup=confirmation_kb,
            parse_mode="Markdown"
        )
    except UserProfile.DoesNotExist:
        # Если профиля нет, сразу просим логин
        await state.set_state(AuthState.waiting_for_login)
        await message.answer("Введите ваш логин от системы:")

# --- Обработчик нажатия на inline-кнопки подтверждения ---
@router.callback_query(AuthState.waiting_for_confirmation)
async def process_auth_confirmation(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer() # "убираем часики" на кнопке
    if callback.data == "auth_confirm_yes":
        await state.set_state(AuthState.waiting_for_login)
        await callback.message.edit_text("Понял. Введите ваш новый логин:")
    else:
        await state.clear()
        await callback.message.edit_text("Операция отменена.")

# --- Обработчик состояния ожидания логина ---
@router.message(AuthState.waiting_for_login)
async def process_auth_login(message: types.Message, state: FSMContext):
    # Сохраняем логин в хранилище состояния
    await state.update_data(login=message.text.strip())
    await state.set_state(AuthState.waiting_for_password)
    await message.answer("Отлично. Теперь введите ваш пароль:")

# --- Обработчик состояния ожидания пароля ---
@router.message(AuthState.waiting_for_password)
async def process_auth_password(message: types.Message, state: FSMContext):

    # Получаем логин из хранилища
    user_data = await state.get_data()
    login = user_data.get('login')
    password = message.text.strip()

    # !!! ВАЖНО: Сразу удаляем сообщение с паролем из чата !!!
    await message.delete()

    # Показываем, что мы работаем
    temp_message = await message.answer("Проверяю данные...")

    # Вызываем нашу асинхронную функцию проверки
    is_valid = await check_user_credentials(login, password)

    if is_valid:
        # Если данные верны, обновляем профиль
        updated = await update_user_telegram_profile(
            username=login,
            telegram_id=message.from_user.id,
            telegram_name=message.from_user.username or ""
        )
        if updated:
            await temp_message.edit_text("✅ Успешно! Ваш аккаунт привязан.")
        else:
            await temp_message.edit_text("❌ Произошла ошибка при обновлении профиля.")
    else:
        await temp_message.edit_text("❌ Неверный логин или пароль. Попробуйте снова, нажав на кнопку 'Привязать аккаунт'.")

    # В любом случае выходим из состояния
    await state.clear()

# --- Обработчик команды /updateinfo и кнопки "Обновить инфо" ---
@router.message(Command("updateinfo"))
@router.message(F.text == "⚠️ Обновить инфо")
async def cmd_update_info_start(message: types.Message, state: FSMContext):
    # --- ПРОВЕРКА ПРАВ ---
    try:
        user_profile = await UserProfile.objects.select_related('user').aget(telegram_id=str(message.from_user.id))
        user_groups = {group.name async for group in user_profile.user.groups.all()}
        if 'Менеджер' not in user_groups:
            await message.answer("❌ У вас нет доступа к этой функции.")
            return
    except UserProfile.DoesNotExist:
        await message.answer("❌ Я вас не узнал. Пожалуйста, привяжите аккаунт.")
        return

    # Если проверка пройдена, начинаем диалог
    await state.set_state(UpdateInfoState.waiting_for_barcodes)
    await message.answer(
        "Пришлите список штрихкодов для обновления.\n"
        "Каждый штрихкод на новой строчке."
    )

# --- Обработчик состояния ожидания штрихкодов ---
@router.message(UpdateInfoState.waiting_for_barcodes)
async def process_update_info_barcodes(message: types.Message, state: FSMContext):
    barcodes = [line.strip() for line in message.text.split('\n') if line.strip()]
    if not barcodes:
        await message.answer("Список штрихкодов не может быть пустым. Попробуйте еще раз.")
        return

    # Сохраняем штрихкоды в FSM и переходим к следующему шагу
    await state.update_data(barcodes=barcodes)
    await state.set_state(UpdateInfoState.waiting_for_info_text)
    await message.answer("Отлично. Теперь введите новое значение для поля 'Info' (описания товара):")

# --- Обработчик состояния ожидания текста для поля Info ---
@router.message(UpdateInfoState.waiting_for_info_text)
async def process_update_info_text(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    barcodes = user_data.get('barcodes', [])
    info_text = message.text # Не используем strip(), чтобы можно было вставить пробелы в начале/конце

    temp_message = await message.answer("🔄 Обновляю информацию в базе данных...")

    # Вызываем нашу асинхронную логику
    result = await update_products_info_by_barcodes(barcodes, info_text)

    # Формируем итоговое сообщение
    updated_count = result.get('updated_count', 0)
    missing_barcodes = result.get('missing_barcodes', [])

    message_lines = [f"✅ Информация обновлена для {updated_count} товаров."]
    if missing_barcodes:
        message_lines.append("\n" + "Не найденные штрихкоды:")
        message_lines.extend(missing_barcodes)

    final_message = "\n".join(message_lines)
    await temp_message.edit_text(final_message)

    # Завершаем диалог
    await state.clear()

# --- Обработчик команды /operations и кнопки "Операции" ---
@router.message(Command("operations"))
@router.message(F.text == "❔ Операции")
async def cmd_operations_start(message: types.Message, state: FSMContext):
    # Эта функция доступна всем, поэтому проверки прав нет
    await state.set_state(OperationsState.waiting_for_barcode)
    await message.answer("Введите штрихкод товара для получения истории операций:")

# --- Обработчик состояния ожидания штрихкода для операций ---
@router.message(OperationsState.waiting_for_barcode)
async def process_operations_barcode(message: types.Message, state: FSMContext):
    barcode = message.text.strip()
    if not barcode:
        await message.answer("Штрихкод не может быть пустым. Попробуйте еще раз.")
        return

    temp_message = await message.answer("🔍 Ищу операции по штрихкоду...")

    # Вызываем нашу асинхронную логику
    operations_message = await get_product_operations_by_barcode(barcode)

    # Редактируем сообщение с результатом
    await temp_message.edit_text(operations_message)

    # Завершаем диалог
    await state.clear()

# --- Обработчик команды и кнопки для старта проверки ШК ---
@router.message(Command("checkbarcodes"))
@router.message(F.text == "🔍 Проверить ШК")
async def cmd_check_barcodes_start(message: types.Message, state: FSMContext):
    await state.set_state(CheckBarcodesState.waiting_for_barcodes)
    await message.answer(
        "Пришлите список штрихкодов, каждый на новой строке."
    )

# --- Обработчик входящих ШК в состоянии ожидания ---
@router.message(CheckBarcodesState.waiting_for_barcodes)
async def process_check_barcodes(message: types.Message, state: FSMContext):
    barcodes = [
        line.strip() for line in message.text.split("\n")
        if line.strip()
    ]
    if not barcodes:
        await message.answer(
            "Список штрихкодов не может быть пустым. Попробуйте еще раз."
        )
        return

    # вызываем нашу логику и получаем HTML-ответ
    result_text = await check_barcodes(barcodes)

    # шлём результат, принимая HTML-разметку hbold/hcode
    await message.answer(
        result_text,
        parse_mode="HTML"
    )
    await state.clear()
