import telebot
#import schedule
import time
import threading
from datetime import datetime, timedelta
import requests
from .botconfig import BACKEND_URL, TELEGRAM_TOKEN
from .dynamic_stats_sender import (
    send_photographers_dynamic_stats,
    send_queue_stats_scheduled,
    send_queue_stats,
    send_queue_stats_okz_scheduled,
    scheduled_order_status_refresh,
    send_product_operations_stats,
    get_daily_moderation_stats_message,
    send_daily_priority_strequests_notification
    )
from .manager import (
    get_product_operations,
    call_update_product_info_endpoint
    )


CHAT_ID = '-1002559221974'  # ID чата для ежедневной рассылки
YOUR_THREAD_ID = '1'
YESTERDAY_STATS_CHAT_ID = '-1002559221974'
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Глобальный словарь для хранения данных диалога по chat_id
conversation_data = {}

#############################################
# Функция для получения статистики (без изменений)
#############################################
def get_stats(date_str):
    """
    Принимает дату в формате dd.mm.yyyy, преобразует в формат ГГГГ-MM-DD
    и делает GET-запрос к эндпоинту для получения статистики за этот день.
    Если данные найдены, формирует текст сообщения с нормальными кириллическими названиями.
    """
    try:
        date_obj = datetime.strptime(date_str, '%d.%m.%Y').date()
    except ValueError:
        return "Неверный формат даты. Используйте: dd.mm.yyyy"

    formatted_date = date_obj.strftime('%Y-%m-%d')
    # Убедитесь, что URL эндпоинта верный
    endpoint_url = f"{BACKEND_URL}/mn/fsallstats/"
    params = {
        "start_date": formatted_date,
        "end_date": formatted_date,
    }

    try:
        # Добавляем таймаут для предотвращения зависания
        response = requests.get(endpoint_url, params=params, timeout=15)
        response.raise_for_status() # Проверяет на HTTP ошибки (4xx, 5xx)
        data = response.json()
    except requests.exceptions.Timeout:
         return f"❌ Ошибка: Сервер не ответил вовремя ({endpoint_url})"
    except requests.exceptions.RequestException as e:
        # Логирование ошибки может быть полезно здесь
        # print(f"Request error: {e}")
        return f"❌ Ошибка при запросе данных к {endpoint_url}. Проверьте доступность сервера."
    except Exception as e: # Ловим другие возможные ошибки (например, JSONDecodeError)
        # print(f"Unexpected error: {e}")
        return f"❌ Произошла непредвиденная ошибка: {str(e)}"

    stats = data.get(formatted_date)
    if not stats:
        # Можно добавить вывод полученного ответа для диагностики
        # print(f"Data received for {formatted_date}: {data}")
        return f"⚠️ Данные за {date_str} не найдены или недоступны."

    # --- Обновленный порядок ключей и эмодзи ---
    keys_order = [
        "Заказано",
        "Принято",
        "Отправлено",
        "Брак товара",
        "Сфотографировано",
        "Отретушировано",
        "Брак по съемке",
        # Новые метрики:
        "Сделано рендеров",
        "Отклонено на рендерах",
        "Загружено рендеров",
        "Загружено фото от фс",
    ]
    emojis = {
        "Заказано": "📦",
        "Принято": "📥",
        "Отправлено": "🚚",
        "Брак товара": "❌",
        "Сфотографировано": "📸",
        "Отретушировано": "🎨",
        "Брак по съемке": "❗",
        # Новые эмодзи:
        "Сделано рендеров": "®", # Альтернативы: ✅, 🖼️
        "Отклонено на рендерах": "🚫", # Альтернативы: 🙅‍♂️, 👎
        "Загружено рендеров": "💾",  # Альтернативы: 📤 (рендеры)
        "Загружено фото от фс": "💾", # Альтернативы: ⬆️ (фото)
    }
    # --- Конец обновлений ---

    display_date = date_obj.strftime('%d.%m.%Y')
    message_lines = [f"📊 *Показатели фотостудии за {display_date}:*",
                       "━━━━━━━━━━━━━━━━"]
    found_metrics = 0
    for key in keys_order:
        # Используем get с дефолтом 0 на случай, если ключ отсутствует в ответе API
        value = stats.get(key, 0)
        # Можно добавить условие, чтобы не выводить метрики с нулевым значением,
        # но обычно лучше показывать все заказанные метрики
        message_lines.append(f"{emojis.get(key, '❓')} {key}: *{value}*")
        if key in stats: # Считаем, сколько метрик реально пришло
            found_metrics += 1

    message_lines.append("━━━━━━━━━━━━━━━━")

    # Дополнительная проверка, если stats есть, но пустой
    if found_metrics == 0 and stats is not None:
         return f"⚠️ Данные за {date_str} получены, но все значения нулевые или отсутствуют."

    return "\n".join(message_lines)

def send_daily_stats():
    today_str = datetime.now().strftime('%d.%m.%Y')
    stats_message = get_stats(today_str)
    
    max_retries = 3  # Количество попыток отправки
    for attempt in range(max_retries):
        try:
            bot.send_message(CHAT_ID, stats_message, parse_mode="Markdown")
            print(f"Статистика отправлена успешно с попытки {attempt + 1}")
            break
        except Exception as e:
            print(f"Ошибка при отправке статистики: {str(e)}. Попытка {attempt + 1} из {max_retries}.")
            if attempt == max_retries - 1:
                print("Не удалось отправить статистику после нескольких попыток.")

def send_yesterday_stats():
    """
    Получает статистику за вчерашний день, используя функцию get_stats,
    и отправляет ее в предопределенный Telegram чат YESTERDAY_STATS_CHAT_ID
    с несколькими попытками в случае ошибки.
    """
    try:
        # 1. Вычисляем вчерашнюю дату
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        # Форматируем дату в нужный для get_stats формат (dd.mm.yyyy)
        yesterday_str_for_get_stats = yesterday.strftime('%d.%m.%Y')
        # Также сохраним формат для логов, если нужно
        yesterday_log_str = yesterday.strftime('%Y-%m-%d')

        print(f"Запрашиваем статистику за {yesterday_str_for_get_stats}...")

        # 2. Получаем сообщение со статистикой за вчера
        stats_message = get_stats(yesterday_str_for_get_stats)

        if stats_message.startswith("❌") or stats_message.startswith("⚠️"):
             print(f"Функция get_stats вернула ошибку или предупреждение: {stats_message}")
             return

    except Exception as e:
        print(f"Критическая ошибка при подготовке данных для отправки статистики за вчера: {e}")
        return 

    # 3. Отправляем сообщение
    max_retries = 3  
    print(f"Попытка отправить статистику за {yesterday_str_for_get_stats} в чат {YESTERDAY_STATS_CHAT_ID}...")

    for attempt in range(max_retries):
        try:
            bot.send_message(
                chat_id=CHAT_ID,
                text=stats_message,
                parse_mode="Markdown",
                message_thread_id=YOUR_THREAD_ID
            )
            print(f"Статистика за {yesterday_str_for_get_stats} успешно отправлена в чат {YESTERDAY_STATS_CHAT_ID} с попытки {attempt + 1}")
            break
        except Exception as e:
            print(f"Ошибка при отправке статистики в чат {YESTERDAY_STATS_CHAT_ID}: {str(e)}. Попытка {attempt + 1} из {max_retries}.")
            if attempt == max_retries - 1:
                print(f"Не удалось отправить статистику за {yesterday_str_for_get_stats} в чат {YESTERDAY_STATS_CHAT_ID} после {max_retries} попыток.")

#############################################
# Обработчики команд (без изменений)
#############################################
@bot.message_handler(commands=['stats'])
def send_stats(message):
    try:
        command = message.text.split()
        # Если пользователь не передал дату, используем сегодняшнюю
        if len(command) == 1:
            date_str = datetime.now().strftime('%d.%m.%Y')
        elif len(command) == 2:
            date_str = command[1]
            # Проверяем формат даты
            try:
                datetime.strptime(date_str, '%d.%m.%Y')
            except ValueError:
                bot.reply_to(message, "Неверный формат даты. Используйте: dd.mm.yyyy")
                return
        else:
            bot.reply_to(message, "Неверное количество параметров. Используйте: /stats [dd.mm.yyyy]")
            return

        stats_message = get_stats(date_str)
        bot.reply_to(message, stats_message, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Произошла ошибка: {str(e)}")

@bot.message_handler(commands=['chatid'])
def send_chatid(message):
    chat_id = message.chat.id
    topic_id = getattr(message, 'message_thread_id', None)
    if topic_id:
        response = f"ID чата: {chat_id}\nID темы: {topic_id}"
    else:
        response = f"ID чата: {chat_id}"
    bot.reply_to(message, response)

@bot.message_handler(commands=['readyphotos'])
def readyphotos_command(message):
    bot.reply_to(message, "Пришлите штрихкоды товаров, каждый на новой строчке")
    bot.register_next_step_handler(message, process_readyphotos)

def process_readyphotos(message):
    try:
        barcodes = [line.strip() for line in message.text.split("\n") if line.strip()]
        if not barcodes:
            bot.reply_to(message, "Не удалось распознать штрихкоды. Попробуйте еще раз.")
            return
        
        barcodes_param = ",".join(barcodes)
        params = {"barcodes": barcodes_param}
        
        response = requests.get(f"{BACKEND_URL}/ft/ready-photos/", params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        not_found = data.get("not_found", [])

        reply_lines = []
        for item in results:
            barcode = item.get("barcode", "неизвестно")
            retouch_link = item.get("retouch_link", "нет ссылки")
            reply_lines.append(f"{barcode} - {retouch_link}")

        if not_found:
            reply_lines.append("Не найдены штрихкоды: " + ", ".join(not_found))
            
        reply_message = "\n".join(reply_lines)
        bot.reply_to(message, reply_message)
    except Exception as e:
        bot.reply_to(message, f"Ошибка при обработке запроса: {str(e)}")

def send_order_accept_message(message_text):
    CHAT_ID_ORDER = '-1002213405207'
    MESSAGE_THREAD_ID = 372
    try:
        bot.send_message(CHAT_ID_ORDER, message_text, parse_mode="Markdown", message_thread_id=MESSAGE_THREAD_ID)
    except Exception as e:
        print(f"Ошибка при отправке сообщения о завершении приемки: {e}")

@bot.message_handler(commands=['queue'])
def handle_queue_command(message):
    # Отправляем сообщение в чат, откуда пришла команда /queue
    send_queue_stats(message.chat.id)


#############################################
#Обработчик команды operations
#############################################

@bot.message_handler(commands=['operations']) #
def operations_command(message): #
    bot.reply_to(message, "Пожалуйста, введите штрихкод товара для получения истории операций:") #
    bot.register_next_step_handler(message, process_barcode_for_operations) #

def process_barcode_for_operations(message): #
    try:
        barcode = message.text.strip() #
        if not barcode: #
            bot.reply_to(message, "Штрихкод не может быть пустым. Пожалуйста, попробуйте команду /operations еще раз.") #
            return #
        
        operations_message = get_product_operations(barcode) #
        bot.reply_to(message, operations_message, parse_mode="Markdown") #

    except Exception as e: #
        error_text = f"❌ Произошла внутренняя ошибка при обработке вашего запроса: {str(e)}" #
        bot.reply_to(message, error_text) #
        print(f"Error in process_barcode_for_operations: {e}") #

#############################################
#Обработчик /updateinfo
#############################################

@bot.message_handler(commands=['updateinfo'])
def updateinfo_command_handler(message): # Функция с таким именем уже есть, но логика меняется
    chat_id = message.chat.id #
    # Проверка прав теперь на стороне бэкенда. Бот просто собирает данные.
    bot.reply_to(message, "Пришлите список штрихкодов (каждый на новой строчке):") #
    # Передаем исходное сообщение message, чтобы потом извлечь message.from_user.id
    bot.register_next_step_handler(message, process_barcodes_for_info_update_via_api)

def process_barcodes_for_info_update_via_api(message): # Новое имя функции во избежание путаницы
    chat_id = message.chat.id #
    try:
        barcodes_text = message.text.strip() #
        if not barcodes_text: #
            bot.reply_to(message, "Список штрихкодов не может быть пустым. Попробуйте /updateinfo еще раз.") #
            return #

        barcodes = [line.strip() for line in barcodes_text.split('\n') if line.strip()] #
        if not barcodes: #
            bot.reply_to(message, "Не найдено корректных штрихкодов в вашем сообщении. Попробуйте /updateinfo еще раз.") #
            return #

        # Сохраняем штрихкоды и ID пользователя Telegram для следующего шага
        conversation_data[chat_id] = { #
            "barcodes_for_updateinfo": barcodes, #
            "telegram_user_id": str(message.from_user.id) # Сохраняем ID пользователя
        }
        
        bot.reply_to(message, "Теперь введите новое значение для поля Info (описания товара):") #
        bot.register_next_step_handler(message, process_new_info_text_via_api)

    except Exception as e: #
        bot.reply_to(message, f"❌ Произошла ошибка при обработке штрихкодов: {str(e)}") #
        if chat_id in conversation_data: #
            del conversation_data[chat_id] #

def process_new_info_text_via_api(message): # Новое имя функции
    chat_id = message.chat.id #
    try:
        new_info_text = message.text.strip() #
        # new_info_text может быть пустой строкой, если пользователь хочет очистить поле Info.

        if chat_id not in conversation_data or \
           "barcodes_for_updateinfo" not in conversation_data[chat_id] or \
           "telegram_user_id" not in conversation_data[chat_id]: #
            bot.reply_to(message, "Не удалось найти сохраненные данные (штрихкоды или ID пользователя). Пожалуйста, начните сначала с команды /updateinfo.") #
            return #

        barcodes_to_update = conversation_data[chat_id]["barcodes_for_updateinfo"] #
        user_telegram_id = conversation_data[chat_id]["telegram_user_id"]

        # Вызываем новую функцию из manager.py, которая обращается к API
        response_message_from_api = call_update_product_info_endpoint(
            user_telegram_id, 
            barcodes_to_update, 
            new_info_text
        )
        
        bot.reply_to(message, response_message_from_api) # Отправляем ответ от API пользователю

    except Exception as e: #
        bot.reply_to(message, f"❌ Произошла внутренняя ошибка при обновлении информации: {str(e)}") #
    finally:
        # Очищаем данные диалога после завершения операции
        if chat_id in conversation_data: #
            del conversation_data[chat_id] #


#############################################
# Новый универсальный метод для отправки сообщения по chat_id
#############################################
def escape_markdown_legacy(text: str) -> str:
    """
    Экранирует специальные символы для Telegram `Markdown` (старая версия).
    """
    # Список символов, которые нужно экранировать в старом Markdown
    escape_chars = ['_']
    
    # Создаем копию текста, чтобы не изменять оригинальную строку
    escaped_text = text
    
    for char in escape_chars:
        # Заменяем каждый спецсимвол на его экранированную версию (например, '_' на '\_')
        escaped_text = escaped_text.replace(char, '\\' + char)
        
    return escaped_text

def send_custom_message(chat_id, message_text, message_thread_id=None):
    """
    Универсальный метод для отправки сообщения в указанный чат
    с автоматическим экранированием Markdown-символов.
    
    Аргументы:
        chat_id: Идентификатор чата, куда отправляется сообщение.
        message_text: Текст сообщения.
        message_thread_id: (необязательный) идентификатор темы, если сообщение отправляется в конкретную тему.
    """
    try:
        # Экранируем текст перед отправкой
        escaped_text = escape_markdown_legacy(message_text)
        
        bot.send_message(
            chat_id,
            escaped_text,  # Отправляем экранированный текст
            parse_mode="Markdown",
            message_thread_id=message_thread_id
        )
    except Exception as e:
        print(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")

def send_custom_message_multiple(chat_ids, message_text, message_thread_id=None):
    """
    Универсальный метод для отправки сообщения в несколько чатов.

    Аргументы:
        chat_ids: Список идентификаторов чатов, куда отправляются сообщения.
        message_text: Текст сообщения.
        message_thread_id: (необязательный) идентификатор темы, если сообщение отправляется в конкретную тему.
    """
    for chat_id in chat_ids:
        try:
            bot.send_message(chat_id, message_text, parse_mode="Markdown", message_thread_id=message_thread_id)
        except Exception as e:
            print(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")

#############################################
# Новый функционал: привязка Telegram ID
#############################################
def check_existing_telegram(chat_id):
    """
    Проверяет, привязан ли уже данный Telegram ID.
    Эндпоинт: /auto/userprofile_by_telegram/
    Принимает параметр telegram_id и возвращает JSON:
    {"exists": True, "username": "user1"} или {"exists": False}
    """
    try:
        url = f"{BACKEND_URL}/auto/userprofile_by_telegram/"
        params = {"telegram_id": chat_id}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ошибка при проверке существующего Telegram ID: {e}")
        return {"exists": False}

def verify_user_credentials(username, password):
    """
    Проверяет учетные данные пользователя.
    Эндпоинт: /auto/verify_credentials/
    Принимает JSON {"username": username, "password": password} и возвращает JSON {"success": True/False}
    """
    try:
        url = f"{BACKEND_URL}/auto/verify_credentials/"
        payload = {"username": username, "password": password}
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("success", False)
    except Exception as e:
        print(f"Ошибка при проверке учетных данных: {e}")
        return False

def update_telegram_profile(username, chat_id, telegram_name):
    """
    Обновляет профиль пользователя, устанавливая Telegram ID и имя.
    Эндпоинт: /auto/update_telegram_id/
    Принимает JSON {"username": username, "telegram_id": chat_id, "telegram_name": telegram_name}
    и возвращает {"success": True/False}
    """
    try:
        url = f"{BACKEND_URL}/auto/update_telegram_id/"
        payload = {
            "username": username,
            "telegram_id": str(chat_id),
            "telegram_name": telegram_name
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("success", False)
    except Exception as e:
        print(f"Ошибка при обновлении профиля: {e}")
        return False

@bot.message_handler(commands=['addtelegramid'])
def add_telegram_id_command(message):
    # Проверяем, что команда вызвана в личном чате
    if message.chat.type != "private":
        return  # Игнорируем команды, вызванные в групповых чатах

    chat_id = message.chat.id
    existing = check_existing_telegram(chat_id)
    if existing.get("exists"):
        username = existing.get("username", "неизвестный пользователь")
        bot.reply_to(message, f"Этот Telegram ID уже привязан к пользователю {username}. Вы хотите перезаписать? (Да/Нет)")
        conversation_data[chat_id] = {"existing": True}
        bot.register_next_step_handler(message, process_confirmation)
    else:
        bot.reply_to(message, "Введите ваш логин:")
        conversation_data[chat_id] = {"existing": False}
        bot.register_next_step_handler(message, process_login)

def process_confirmation(message):
    chat_id = message.chat.id
    answer = message.text.strip().lower()
    if answer == "да":
        bot.reply_to(message, "Введите ваш логин:")
        bot.register_next_step_handler(message, process_login)
    else:
        bot.reply_to(message, "Операция отменена.")
        conversation_data.pop(chat_id, None)

def process_login(message):
    chat_id = message.chat.id
    login = message.text.strip()
    conversation_data.setdefault(chat_id, {})["login"] = login
    bot.reply_to(message, "Введите ваш пароль:")
    bot.register_next_step_handler(message, process_password)

def process_password(message):
    chat_id = message.chat.id
    password = message.text.strip()
    conversation_data.setdefault(chat_id, {})["password"] = password
    login = conversation_data[chat_id].get("login")
    telegram_username = message.from_user.username if message.from_user.username else ""
    if verify_user_credentials(login, password):
        if update_telegram_profile(login, chat_id, telegram_username):
            bot.reply_to(message, "Ваш Telegram ID успешно привязан к вашему аккаунту.")
        else:
            bot.reply_to(message, "Ошибка при обновлении профиля. Попробуйте позже.")
    else:
        bot.reply_to(message, "Неверные учетные данные. Попробуйте снова.")
    conversation_data.pop(chat_id, None)

#############################################
# Планировщик для ежедневной отправки статистики в 20:30
#############################################
def scheduler_thread():
    # Существующий job для ежедневной рассылки статистики в 20:30
    schedule.every().day.at("20:08").do(send_daily_stats)
    schedule.every().day.at("12:25").do(send_yesterday_stats)
    
    schedule.every().day.at("12:29").do(send_photographers_dynamic_stats)
    schedule.every().day.at("16:59").do(send_photographers_dynamic_stats)
    schedule.every().day.at("20:03").do(send_photographers_dynamic_stats)

    schedule.every().day.at("07:55").do(send_queue_stats_scheduled)
    schedule.every().day.at("08:00").do(send_queue_stats_okz_scheduled)
    schedule.every().day.at("20:00").do(send_queue_stats_okz_scheduled)

    schedule.every().day.at("07:59").do(scheduled_order_status_refresh)
    schedule.every().day.at("19:59").do(scheduled_order_status_refresh)

    schedule.every().day.at("12:28").do(send_product_operations_stats)
    schedule.every().day.at("16:58").do(send_product_operations_stats)
    schedule.every().day.at("19:58").do(send_product_operations_stats)

    schedule.every().day.at("20:01").do(get_daily_moderation_stats_message)

    schedule.every().day.at("07:45").do(send_daily_priority_strequests_notification)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

#############################################
# Основной цикл работы бота
#############################################
def run_bot():
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except requests.exceptions.ReadTimeout:
            print("Таймаут подключения. Перезапуск...")
        except Exception as e:
            print(f"Произошла ошибка: {str(e)}. Перезапуск...")

if __name__ == "__main__":
    scheduler = threading.Thread(target=scheduler_thread)
    scheduler.daemon = True
    scheduler.start()
    run_bot()
