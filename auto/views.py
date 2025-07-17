import uuid
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Q
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django_q.tasks import async_task
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from datetime import timedelta
from core.models import (
    STRequest,
    STRequestProduct,
    UserProfile,
    Order,
    OrderStatus
    )

from django_q.tasks import async_task
from .models import RGTScripts


#Удалить заявки с 0 товаров
class DeleteEmptyRequestsView(APIView):
    def delete(self, request, format=None):
        # Аннотируем количество связанных записей и фильтруем запросы с 0 товарами
        empty_requests = STRequest.objects.annotate(product_count=Count('strequestproduct')).filter(product_count=0)
        deleted_count = empty_requests.count()
        empty_requests.delete()
        return Response({'deleted_requests': deleted_count}, status=status.HTTP_200_OK)

#Перевести застрявшие заявки
class UpdateStuckRequestsView(APIView):
    def post(self, request, format=None):
        # Выбираем все заявки, у которых статус = 3 (предполагается, что status_id хранит идентификатор статуса)
        stuck_requests = STRequest.objects.filter(status_id=3)
        updated_count = 0

        for req in stuck_requests:
            # Получаем все связанные записи STRequestProduct для данной заявки
            products = req.strequestproduct_set.all()

            # Если заявка имеет хотя бы один товар и для всех записей sphoto_status_id равен 1
            if products.exists() and all(product.sphoto_status_id == 1 for product in products):
                req.status_id = 5  # Меняем статус заявки на 5
                req.save()
                updated_count += 1

        return Response({'updated_requests': updated_count}, status=status.HTTP_200_OK)

def userprofile_by_telegram(request):
    """
    GET-запрос с параметром telegram_id.
    Если профиль найден, возвращает {"exists": True, "username": <username>},
    иначе {"exists": False}.
    """
    telegram_id = request.GET.get('telegram_id')
    if not telegram_id:
        return JsonResponse({"error": "telegram_id parameter is required"}, status=400)
    try:
        profile = UserProfile.objects.get(telegram_id=telegram_id)
        return JsonResponse({"exists": True, "username": profile.user.username})
    except UserProfile.DoesNotExist:
        return JsonResponse({"exists": False})

@csrf_exempt
def verify_credentials(request):
    """
    POST-запрос с JSON-данными {"username": <username>, "password": <password>}.
    Если данные корректны, возвращает {"success": True}, иначе {"success": False}.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)
    try:
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    if not username or not password:
        return JsonResponse({"success": False, "error": "Username and password are required"}, status=400)

    user = authenticate(username=username, password=password)
    if user:
        return JsonResponse({"success": True})
    else:
        return JsonResponse({"success": False, "error": "Invalid credentials"})

@csrf_exempt
def update_telegram_id(request):
    """
    POST-запрос с JSON-данными {"username": <username>, "telegram_id": <telegram_id>, "telegram_name": <telegram_name>}.
    Обновляет профиль пользователя, устанавливая указанный telegram_id и telegram_name.
    Возвращает {"success": True} при успехе.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method is allowed"}, status=405)
    try:
        data = json.loads(request.body)
        username = data.get("username")
        telegram_id = data.get("telegram_id")
        telegram_name = data.get("telegram_name", "")
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    if not username or not telegram_id:
        return JsonResponse({"success": False, "error": "username and telegram_id are required"}, status=400)

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({"success": False, "error": "User does not exist"}, status=404)

    profile, created = UserProfile.objects.get_or_create(user=user)
    profile.telegram_id = telegram_id
    profile.telegram_name = telegram_name
    profile.save()
    return JsonResponse({"success": True})

#сброс заказов
def order_status_refresh(request):
    try:
        rgt_settings = RGTScripts.load()  # Загружаем настройки, используя ваш метод load()
    except Exception as e:
        # Здесь можно добавить логирование ошибки e
        return JsonResponse({"error": "Не удалось загрузить настройки РГТ. Обратитесь к администратору."}, status=500)

    # Проверяем флаг OKZReorderEnable
    if not rgt_settings.OKZReorderEnable:
        # Если сброс отключен, возвращаем сообщение согласно вашему требованию
        return JsonResponse({"message": "Нет заказов, удовлетворяющих условиям."}, status=200)

    # Получаем порог из настроек
    threshold_duration = rgt_settings.OKZReorderTreshold

    # Проверяем, установлено ли значение порога
    if threshold_duration is None:
        return JsonResponse({
            "error": "Сброс заказов включен (OKZReorderEnable=True), но отсечка сброса (OKZReorderTreshold) не установлена в настройках РГТ."
        }, status=400) # HTTP 400 Bad Request, т.к. конфигурация неполная

    # Рассчитываем пороговую дату
    threshold_date = timezone.now() - threshold_duration

    # Получаем статусы с id=3 и id=2
    try:
        status_3 = OrderStatus.objects.get(id=3)
        status_2 = OrderStatus.objects.get(id=2)
    except OrderStatus.DoesNotExist:
        # Можно улучшить сообщение об ошибке, указав, какой статус не найден,
        # но для простоты оставим как в вашем оригинальном коде.
        return JsonResponse({"error": "Не найден один из требуемых статусов заказа."}, status=400)

    # Фильтруем заказы для обновления
    orders_to_update = Order.objects.filter(status=status_3, assembly_date__lt=threshold_date)

    if not orders_to_update.exists():
        return JsonResponse({"message": "Нет заказов, удовлетворяющих условиям."}, status=200)

    updated_orders = []
    for order in orders_to_update:
        order.status = status_2
        order.assembly_date = None  # Очищаем дату сборки
        order.save()
        updated_orders.append({
            "OrderNumber": order.OrderNumber,
            "date": order.date.isoformat() if order.date else None,  # Рекомендуется форматировать дату для JSON
            "status": order.status.name,  # Здесь будет имя status_2
            "assembly_date": order.assembly_date,  # Будет None
        })

    return JsonResponse({"updated_orders": updated_orders}, status=200)

#проставить чек тайм, удалить потом
@csrf_exempt
@require_http_methods(["POST"]) # Рекомендуется POST для операций, изменяющих данные
def update_strequest_check_time_directly(request):
    """
    Обновляет поле check_time для STRequest со статусом 5
    и где check_time не установлено, без использования Celery.
    """
    try:
        now = timezone.now()
        
        # Фильтруем STRequest по status_id=5 (или status__id=5, если status это ForeignKey)
        # и check_time is null или blank
        # Предполагаем, что 'status' - это ForeignKey к модели статусов, поэтому используем status__id
        requests_to_update = STRequest.objects.filter(
            status__id=5,
            check_time__isnull=True
        )
        
        # Эффективно обновляем все найденные записи одним запросом к БД
        updated_count = requests_to_update.update(check_time=now)
        
        return JsonResponse({
            "message": "Операция обновления check_time завершена.",
            "updated_records": updated_count
        }, status=200)
        
    except Exception as e:
        # Базовая обработка ошибок
        return JsonResponse({
            "error": "Произошла ошибка при обновлении записей.",
            "details": str(e)
        }, status=500)

#Ручной запуск скрипта IsOnOrder
@api_view(['POST']) # Указываем, что эта view принимает только POST запросы
@permission_classes([IsAuthenticated]) # Требуем, чтобы пользователь был аутентифицирован
def trigger_update_order_status_task(request):
    """
    Запускает асинхронную задачу update_render_product_is_on_order_status
    и возвращает уникальный ID для отслеживания на фронтенде.
    """
    # Проверка "if request.method == 'POST'" больше не нужна,
    # так как декоратор @api_view уже сделал это за нас.
    try:
        # 1. Генерируем уникальный ID для этой конкретной сессии
        frontend_task_id = str(uuid.uuid4())
        # Теперь request.user гарантированно будет реальным пользователем
        user_id = request.user.id

        # 2. Запускаем задачу, передавая ей user_id и сгенерированный task_id
        async_task(
            'auto.tasks.update_render_product_is_on_order_status',
            user_id=user_id,
            task_id=frontend_task_id
        )
        
        # 3. Возвращаем этот же ID на фронтенд
        return JsonResponse({
            'status': 'success',
            'message': 'Задача успешно запущена.',
            'task_id': frontend_task_id
        })
    except Exception as e:
        # Для DRF лучше использовать его собственный Response
        from rest_framework.response import Response
        from rest_framework import status
        return Response(
            {'status': 'error', 'message': f'Ошибка при запуске задачи: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
