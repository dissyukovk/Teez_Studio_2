# telegram_bot/views.py
import json
from aiogram import Bot, Dispatcher, types
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

# Импортируем наши экземпляры бота и диспетчера
from .bot_instance import bot, dp

@csrf_exempt
async def telegram_webhook(request):
    """
    Эта view принимает обновления от Telegram и передает их диспетчеру aiogram.
    """
    if request.method == "POST":
        try:
            # Преобразуем JSON-строку от Telegram в объект Update
            update = types.Update.model_validate(json.loads(request.body), context={"bot": bot})
            # Передаем обновление в диспетчер для обработки
            await dp.feed_update(bot=bot, update=update)
        except Exception as e:
            # В случае ошибки можно логировать ее
            print(f"Error processing update: {e}")
        finally:
            # Возвращаем Telegram ответ 200 OK, подтверждая, что мы получили обновление
            return HttpResponse(status=200)
    else:
        return HttpResponse("Method Not Allowed", status=405)
