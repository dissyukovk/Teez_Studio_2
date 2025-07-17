# photographers.py
import requests
import logging # Рекомендуется для логирования

# Предполагается, что botconfig.py находится в том же каталоге или пакете
# и содержит BACKEND_URL.
try:
    from .botconfig import BACKEND_URL
except ImportError:
    # Фолбэк, если запускается не как часть пакета (например, для тестов)
    # В рабочей среде .botconfig должен быть доступен
    logging.warning("Could not import BACKEND_URL from .botconfig. Relative import failed.")
    # Установите значение по умолчанию или обработайте ошибку, если это критично
    BACKEND_URL = "http://127.0.0.1:8000" # Пример, замените или удалите


def fetch_priority_strequests_data():
    """
    Получает данные о заявках на съемку с эндпоинта /ph/strequests2/.
    Возвращает список результатов или None в случае ошибки.
    """
    # Убедитесь, что URL эндпоинта правильный
    api_url = f"{BACKEND_URL}/ph/strequests2/?format=json"
    try:
        response = requests.get(api_url, timeout=15) # Таймаут 15 секунд
        response.raise_for_status()  # Проверка на HTTP ошибки (4xx, 5xx)
        data = response.json()
        return data.get("results", []) # Возвращаем список 'results' или пустой список, если ключа нет
    except requests.exceptions.Timeout:
        logging.error(f"Таймаут при запросе приоритетных заявок с {api_url}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе приоритетных заявок с {api_url}: {e}")
        return None
    except ValueError: # Ошибка декодирования JSON
        logging.error(f"Ошибка декодирования JSON ответа с {api_url}")
        return None

def format_priority_strequests_message(strequests_results):
    """
    Форматирует список заявок на съемку в сообщение для Telegram.
    Берет первые 10 заявок.
    Возвращает отформатированную строку или None, если нет данных для отправки.
    """
    if not strequests_results: # Обработка None или пустого списка
        logging.info("Нет данных о заявках для форматирования сообщения.")
        return None

    # Берем первые 10 заявок (или меньше, если их меньше 10)
    top_requests = strequests_results[:10]

    if not top_requests: # Если после среза список пуст (например, results был пустым)
        logging.info("Список топ-10 заявок пуст, сообщение не будет сформировано.")
        return None

    message_lines = ["Наиболее приоритетные заявки, нужно отснять сегодня:"]
    for req in top_requests:
        req_number = req.get("RequestNumber", "Номер не указан")
        total_products = req.get("total_products", "N/A") # total_products приходит как int
        message_lines.append(f"{req_number} - {total_products}")
    
    return "\n".join(message_lines)
