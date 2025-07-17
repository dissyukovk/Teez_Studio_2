# manager.py
import requests
from datetime import datetime
import ast # For safely evaluating string-represented dicts/lists

# Предполагается, что botconfig.py находится в том же каталоге
# и содержит BACKEND_URL.
# Если botconfig.py находится в другом месте, исправьте путь импорта.
from .botconfig import BACKEND_URL #

def _format_datetime_string(iso_datetime_str): #
    """
    Преобразует строку ISO datetime в формат 'YYYY-MM-DD HH:MM:SS'.
    """
    if not iso_datetime_str: #
        return "N/A" #
    try:
        dt_object = datetime.fromisoformat(iso_datetime_str) #
        return dt_object.strftime('%Y-%m-%d %H:%M:%S') #
    except (ValueError, TypeError): #
        try:
            dt_object = datetime.strptime(iso_datetime_str.split('.')[0], "%Y-%m-%dT%H:%M:%S") #
            return dt_object.strftime('%Y-%m-%d %H:%M:%S') #
        except:
            return iso_datetime_str #

def get_product_operations(barcode: str): #
    """
    Получает историю операций по товару для заданного штрихкода с бэкенд API.
    Форматирует операции в удобную для пользователя строку.
    (Эта функция остается из вашего предыдущего файла manager.py)
    """
    api_url = f"{BACKEND_URL}/ft/product-operations/" #
    params = { #
        "page": 1, #
        "page_size": 50, #
        "ordering": "-date", #
        "barcode": barcode #
    }

    try:
        response = requests.get(api_url, params=params, timeout=20) #
        response.raise_for_status() #
        data = response.json() #
    except requests.exceptions.Timeout: #
        return f"❌ Ошибка: Сервер не ответил вовремя ({api_url})" #
    except requests.exceptions.HTTPError as http_err: #
        if response.status_code == 404: #
            error_data = response.json() if response.content else {} #
            if barcode in error_data.get("not_found_barcodes", []): #
                 return "записей не обнаружено" #
            return f"❌ Ошибка HTTP: Ресурс не найден (404) по адресу {api_url}. Возможно, неверный штрихкод или эндпоинт." #
        return f"❌ Ошибка HTTP: {http_err} (Код: {response.status_code}, URL: {api_url})" #
    except requests.exceptions.RequestException as req_err: #
        return f"❌ Ошибка подключения: {req_err} ({api_url})" #
    except ValueError: #
        return "❌ Ошибка: Не удалось декодировать ответ от сервера (неверный JSON)." #

    results = data.get("results", []) #

    if not results: #
        if barcode in data.get("not_found_barcodes", []): #
            return "записей не обнаружено" #
        return "записей не обнаружено" #


    message_lines = [] #
    if results: #
        first_item = results[0] #
        name = first_item.get("name", "Название неизвестно") #
        message_lines.append(f"Операции для товара: *{name}* (ШК: {barcode})") #
        message_lines.append("------------------------------------") #


    for op in results: #
        date_str = _format_datetime_string(op.get("date")) #
        operation_type = op.get("operation_type", "N/A") #
        user = op.get("user", "N/A") #
        
        comment_val = op.get("comment") #
        comment_str = "" #

        if comment_val is not None: #
            if isinstance(comment_val, str): #
                if comment_val.startswith('{') and comment_val.endswith('}'): #
                    try:
                        parsed_comment = ast.literal_eval(comment_val) #
                        if isinstance(parsed_comment, dict): #
                            comment_str = ", ".join(f"{k} {v}" for k, v in parsed_comment.items()) #
                        else:
                            comment_str = str(parsed_comment) #
                    except (ValueError, SyntaxError): #
                        comment_str = comment_val #
                else:
                    comment_str = comment_val #
            else:
                comment_str = str(comment_val) #
        
        message_lines.append(f"{date_str} - {operation_type} - {user}") #

    return "\n".join(message_lines) #


# НОВАЯ ФУНКЦИЯ для вызова эндпоинта обновления информации
def call_update_product_info_endpoint(telegram_id: str, barcodes: list, info_text: str):
    """
    Вызывает эндпоинт на бэкенде для обновления информации о товарах.
    Возвращает отформатированное сообщение для пользователя.
    """
    # Убедитесь, что этот URL совпадает с тем, что вы прописали в urls.py Django
    endpoint_url = f"{BACKEND_URL}/mn/update_info_tgbot/" 
    payload = {
        "telegram_id": str(telegram_id), # Передаем как строку
        "barcodes": barcodes,
        "info": info_text # Эндпоинт ожидает поле 'info'
    }

    try:
        response = requests.post(endpoint_url, json=payload, timeout=25) # Таймаут 25 секунд
        
        if response.status_code == 200:
            data = response.json()
            updated_count = data.get("updated_count", 0)
            missing_barcodes = data.get("missing_barcodes", [])
            
            message_lines = [f"Информация обновлена для {updated_count} товаров."]
            if missing_barcodes:
                message_lines.append("\nНе найденные штрихкоды:")
                message_lines.extend(missing_barcodes) # Добавляем каждый штрихкод как отдельный элемент
            # Можно добавить сообщение, если все штрихкоды найдены и обработаны
            # else:
            #    message_lines.append("Все указанные штрихкоды были найдены и обработаны (если существовали).")
            return "\n".join(message_lines)
        
        elif response.status_code == 403: # Ошибка доступа (нет прав или TG ID не найден)
            try:
                error_data = response.json()
                # Используем сообщение об ошибке от бэкенда, если оно есть
                return f"❌ Ошибка доступа: {error_data.get('error', 'У вас нет роли менеджера или ваш Telegram ID не найден.')}"
            except ValueError: # Если ответ не JSON
                return "❌ Ошибка доступа: У вас нет доступа к этой функции (ответ сервера не в формате JSON)."
        
        elif response.status_code == 400: # Ошибка в параметрах запроса
            try:
                error_data = response.json()
                return f"❌ Ошибка входных данных: {error_data.get('error', 'Неверные параметры запроса.')}"
            except ValueError:
                return "❌ Ошибка входных данных: Неверные параметры запроса (ответ сервера не в формате JSON)."
        
        else: # Другие HTTP ошибки от сервера
            try:
                error_data = response.json()
                error_detail = error_data.get('error', response.text) # Пытаемся извлечь 'error' или весь текст ответа
            except ValueError:
                error_detail = response.text # Если не JSON, берем текст как есть
            return f"❌ Ошибка сервера ({response.status_code}): {error_detail}"

    except requests.exceptions.Timeout:
        return f"❌ Ошибка: Сервер не ответил вовремя ({endpoint_url})"
    except requests.exceptions.RequestException as e: # Более общая ошибка сети/подключения
        return f"❌ Ошибка подключения к серверу: {str(e)}"
    except ValueError: # Если ошибка при вызове response.json() на успешном, но некорректном ответе
        return "❌ Ошибка: Не удалось обработать ответ от сервера (неверный формат)."
