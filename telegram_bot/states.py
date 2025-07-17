# telegram_bot/states.py
from aiogram.fsm.state import State, StatesGroup

class StatsState(StatesGroup):
    # Определяем одно состояние: ожидание ввода даты
    waiting_for_date = State()

class ReadyPhotosState(StatesGroup):
    waiting_for_barcodes = State()

class AuthState(StatesGroup):
    waiting_for_confirmation = State()
    waiting_for_login = State()
    waiting_for_password = State()

class UpdateInfoState(StatesGroup):
    waiting_for_barcodes = State()
    waiting_for_info_text = State()

class OperationsState(StatesGroup):
    waiting_for_barcode = State()

class CheckBarcodesState(StatesGroup):
    waiting_for_barcodes = State()
