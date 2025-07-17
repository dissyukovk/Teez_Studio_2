#render.views
import json
import django_filters
import math
from collections import defaultdict
from django.shortcuts import render
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Case, When, Value, IntegerField, Prefetch, Count, Avg, F, DurationField, Max
from django.db.models.functions import TruncDate, Now
from django.contrib.auth.models import Group, User
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from django_q.tasks import async_task
from rest_framework.generics import ListAPIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from rest_framework import status, generics
from datetime import datetime, time, timedelta, MINYEAR
from .permissions import IsModeratorUser
from .models import (
    Product,
    Render,
    RetouchStatus,
    SeniorRetouchStatus,
    ModerationUpload,
    UploadStatus,
    RejectedReason,
    StudioRejectedReason,
    ModerationStudioUpload,
    RenderCheckResult
    )
from core.models import (
    RetouchRequestProduct,
    UserProfile,
    ProductOperation,
    ProductOperationTypes,
    RetouchRequestProduct,
    Product as CoreProduct,
    ProductCategory,
    Blocked_Shops,
    Blocked_Barcode,
    Nofoto
    )

from .serializers import (
    RetoucherRenderSerializer,
    SeniorRenderSerializer,
    ModerationUploadRejectSerializer,
    ModerationStudioUploadSerializer
    )
from .filters import (
    CharInFilter,
    RenderFilter
    )
from .pagination import StandardResultsSetPagination


#Получение нового шк для рендера
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def StartCheck(request):
    retoucher = request.user
    retouch_status_in_progress_id = 1  # ID статуса "в работе"
    retouch_status_accepted_id = 2     # ID статуса "принято"
    retouch_status_declined_id = 5     # ID статуса "отклонено"
    accepted_limit = 100               # Лимит принятых работ

    # 1. Проверяем лимит принятых работ СНАЧАЛА
    # Делаем это до поиска активной задачи, чтобы не тратить ресурсы зря
    # Note: Пересчитываем здесь, т.к. он нужен и для лимита, и для ответа
    accepted_count = Render.objects.filter(
        Retoucher=retoucher,
        RetouchStatus__id=retouch_status_accepted_id
    ).count()
    if accepted_count > accepted_limit:
        return Response(
            {"error": f"Количество принятых ({accepted_count}) более {accepted_limit}, отправьте рендеры на проверку"},
            status=400
        )

    # 2. Ищем существующий активный Render у этого ретушера
    existing_render = Render.objects.filter(
        Retoucher=retoucher,
        RetouchStatus__id=retouch_status_in_progress_id
    ).select_related('Product').first() # select_related для оптимизации

    # 3. Если найден активный Render, возвращаем его данные
    if existing_render:
        # Пересчитываем отклоненные для актуальности в ответе
        declined_count = Render.objects.filter(
            Retoucher=retoucher,
            RetouchStatus__id=retouch_status_declined_id
        ).count()

        response_data = {
            "id": existing_render.id,
            "Barcode": existing_render.Product.Barcode,
            "Name": existing_render.Product.Name,
            "CategoryName": existing_render.Product.CategoryName,
            "CategoryID": existing_render.Product.CategoryID,
            "ShopID": existing_render.Product.ShopID,
            "ProductID": existing_render.Product.ProductID,
            "SKUID": existing_render.Product.SKUID,
            "declined": declined_count,
            "accepted": accepted_count, # Используем уже посчитанный для лимита
        }
        # Возвращаем статус 200 OK, так как ресурс уже существует
        return Response(response_data, status=200)

    # 4. Если активного Render нет, ищем новый Product и создаем Render
    try:
        with transaction.atomic():
            # Ищем подходящий Product, блокируя его для предотвращения гонки состояний
            product_qs = Product.objects.select_for_update().filter(
                Q(IsOnRender=False) | Q(IsOnRender__isnull=True),
                Q(IsRetouchBlock=False) | Q(IsRetouchBlock__isnull=True),
                Q(IsModerationBlock=False) | Q(IsModerationBlock__isnull=True),
                PhotoModerationStatus__in=["Отклонено"],
                #WMSQuantity__gt=0
            ).annotate(
                status_priority=Case(
                    When(PhotoModerationStatus="Отклонено", then=Value(1)),
                    default=Value(3),
                    output_field=IntegerField()
                )
            ).order_by('status_priority', '-WMSQuantity') # <-- Добавил select_for_update()

            product = product_qs.first()
            if not product:
                return Response({"message": "Подходящие штрихкоды закончились"}, status=404)

            # Обновляем флаг на продукте
            product.IsOnRender = True
            product.save(update_fields=["IsOnRender"])

            # Получаем статус ретуши "в работе" (id=1)
            try:
                retouch_status_started = RetouchStatus.objects.get(id=retouch_status_in_progress_id)
            except RetouchStatus.DoesNotExist:
                 # Критическая ошибка конфигурации
                print(f"CRITICAL ERROR: RetouchStatus with ID={retouch_status_in_progress_id} not found!")
                return Response({"message": "Ошибка конфигурации: не найден статус ретуши."}, status=500)

            # Создаем новый Render
            new_render = Render.objects.create(
                Product=product,
                Retoucher=retoucher,
                CheckTimeStart=timezone.now(), # Время начала проверки/взятия в работу
                RetouchStatus=retouch_status_started
            )

        # После успешной транзакции:
        # Снова считаем отклоненные (т.к. мог измениться статус пока искали)
        declined_count = Render.objects.filter(
            Retoucher=retoucher,
            RetouchStatus__id=retouch_status_declined_id
        ).count()
        # Accepted_count уже посчитан в начале

        # Формируем ответ для нового Render
        response_data = {
            "id": new_render.id,
            "Barcode": new_render.Product.Barcode, # Доступ через new_render.Product
            "Name": new_render.Product.Name,
            "CategoryName": new_render.Product.CategoryName,
            "CategoryID": new_render.Product.CategoryID,
            "ShopID": new_render.Product.ShopID,
            "ProductID": new_render.Product.ProductID,
            "SKUID": new_render.Product.SKUID,
            "declined": declined_count,
            "accepted": accepted_count,
        }
        # Возвращаем статус 201 Created, так как ресурс был создан
        return Response(response_data, status=201)

    except Exception as e:
        # Логирование ошибки
        print(f"Error during StartCheck transaction: {e}") # Используйте logging
        return Response({"message": "Произошла ошибка при назначении задания на ретушь."}, status=500)

#Получение листа проверенных у ретушера
class RetoucherRenderList(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RetoucherRenderSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Render.objects.filter(
            Retoucher=self.request.user,
            RetouchStatus__id__in=[1, 2, 5]
        )
        # Фильтрация по полю IsSuitable, если передан query параметр is_suitable
        is_suitable = self.request.query_params.get('is_suitable')
        if is_suitable is not None:
            if is_suitable.lower() in ['true', '1']:
                queryset = queryset.filter(IsSuitable=True)
            elif is_suitable.lower() in ['false', '0']:
                queryset = queryset.filter(IsSuitable=False)
        # Сортировка: новые в начале
        queryset = queryset.order_by('-created_at')
        # Оптимизация запросов
        queryset = queryset.select_related('Product', 'RetouchStatus').prefetch_related('CheckResult')
        return queryset

#Проверка одного шк ретушером
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def UpdateRender(request, render_id):
    try:
        render_obj = Render.objects.get(pk=render_id)
    except Render.DoesNotExist:
        return Response({"message": "Не найдена запись."}, status=404)

    # Проверяем, что текущий пользователь является Retoucher данного Render
    if render_obj.Retoucher != request.user:
        return Response({"message": "У вас нет прав на изменение этого шк."}, status=403)

    # Получаем данные из запроса
    check_result_ids = request.data.get("CheckResult")  # ожидается список id
    check_comment = request.data.get("CheckComment")
    is_suitable = request.data.get("IsSuitable")
    retouch_photos_link = request.data.get("RetouchPhotosLink")  # опциональное поле

    if is_suitable is None:
        return Response({"message": "Укажите, подходит ли шк для рендера."}, status=400)

    # Приводим is_suitable к булевому значению, если пришёл в виде строки
    if isinstance(is_suitable, str):
        if is_suitable.lower() in ['true', '1']:
            is_suitable = True
        elif is_suitable.lower() in ['false', '0']:
            is_suitable = False
        else:
            return Response({"message": "Неверное значение для пригодности на рендер."}, status=400)

    # Обновляем CheckComment, если передан
    if check_comment is not None:
        render_obj.CheckComment = check_comment

    # Обновляем IsSuitable
    render_obj.IsSuitable = is_suitable

    # Если IsSuitable=True, устанавливаем RetouchTimeStart = now
    if is_suitable:
        render_obj.RetouchTimeStart = timezone.now()

    # Устанавливаем RetouchStatus согласно значению IsSuitable
    new_status_id = 2 if is_suitable else 5
    try:
        retouch_status = RetouchStatus.objects.get(id=new_status_id)
    except RetouchStatus.DoesNotExist:
        return Response({"message": f"RetouchStatus with id={new_status_id} not found."}, status=500)
    render_obj.RetouchStatus = retouch_status

    # Обновляем RetouchPhotosLink, если передан.
    # Если передан RetouchPhotosLink, то ставим RetouchTimeEnd = now
    if retouch_photos_link is not None:
        render_obj.RetouchPhotosLink = retouch_photos_link
        render_obj.RetouchTimeEnd = timezone.now()

    render_obj.save()

    # Обновляем ManyToMany связь CheckResult, если передан список id
    if check_result_ids is not None:
        if not isinstance(check_result_ids, list):
            return Response({"message": "Результаты проверки должны быть списком ID."}, status=400)
        render_obj.CheckResult.set(check_result_ids)

    return Response({"message": "Запись успешно обновлена."}, status=200)

#Проставить правку
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def UpdateRenderEdit(request, render_id):
    try:
        render_obj = Render.objects.get(pk=render_id)
    except Render.DoesNotExist:
        return Response({"message": "Не найдена запись."}, status=404)

    # Проверяем, что текущий пользователь является Retoucher данного Render
    if render_obj.Retoucher != request.user:
        return Response({"message": "У вас нет прав на изменение этого шк."}, status=403)

    # Получаем данные из запроса
    check_result_ids = request.data.get("CheckResult")  # ожидается список id
    check_comment = request.data.get("CheckComment")
    is_suitable = request.data.get("IsSuitable")
    retouch_photos_link = request.data.get("RetouchPhotosLink")  # опциональное поле

    if is_suitable is None:
        return Response({"message": "Укажите, подходит ли шк для рендера."}, status=400)

    # Приводим is_suitable к булевому значению, если пришёл в виде строки
    if isinstance(is_suitable, str):
        if is_suitable.lower() in ['true', '1']:
            is_suitable = True
        elif is_suitable.lower() in ['false', '0']:
            is_suitable = False
        else:
            return Response({"message": "Неверное значение для пригодности на рендер."}, status=400)

    # Обновляем CheckComment, если передан
    if check_comment is not None:
        render_obj.CheckComment = check_comment

    # Обновляем IsSuitable
    render_obj.IsSuitable = is_suitable
    
    if is_suitable:
        senior_retouchers = User.objects.filter(
            groups__name="Старший ретушер",
            profile__on_work=True
        )
        retoucher_name = f"{render_obj.Retoucher.first_name} {render_obj.Retoucher.last_name}" if (render_obj.Retoucher.first_name or render_obj.Retoucher.last_name) else "Не указан"
        message_text = f"{retoucher_name} прислал на проверку правки"
        for senior in senior_retouchers:
            if hasattr(senior, 'profile') and senior.profile.telegram_id:
                async_task(
                    'telegram_bot.tasks.send_message_task',
                    chat_id=senior.profile.telegram_id,
                    text=message_text
                )

    # Если IsSuitable=True, устанавливаем RetouchTimeStart = now
    if is_suitable:
        render_obj.RetouchTimeStart = timezone.now()

    # Устанавливаем RetouchStatus согласно значению IsSuitable
    new_status_id = 3 if is_suitable else 7
    try:
        retouch_status = RetouchStatus.objects.get(id=new_status_id)
    except RetouchStatus.DoesNotExist:
        return Response({"message": f"RetouchStatus with id={new_status_id} not found."}, status=500)
    render_obj.RetouchStatus = retouch_status

    # Обновляем RetouchPhotosLink, если передан.
    # Если передан RetouchPhotosLink, то ставим RetouchTimeEnd = now
    if retouch_photos_link is not None:
        render_obj.RetouchPhotosLink = retouch_photos_link
        render_obj.RetouchTimeEnd = timezone.now()

    render_obj.save()

    # Обновляем ManyToMany связь CheckResult, если передан список id
    if check_result_ids is not None:
        if not isinstance(check_result_ids, list):
            return Response({"message": "Результаты проверки должны быть списком ID."}, status=400)
        render_obj.CheckResult.set(check_result_ids)

    return Response({"message": "Запись успешно обновлена."}, status=200)

#Загрузка ссылок в шк - массовая
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def MassUpdateRetouchPhotosLink(request):
    data = request.data
    if not isinstance(data, list):
        return Response({"message": "Данные должны быть массивом объектов."}, status=400)

    now = timezone.now()
    updated_ids = []

    for item in data:
        render_id = item.get("id")
        retouch_photos_link = item.get("RetouchPhotosLink")
        if render_id is None or retouch_photos_link is None:
            return Response({"message": "Каждый объект должен содержать id и RetouchPhotosLink."}, status=400)

        try:
            render_obj = Render.objects.get(pk=render_id)
        except Render.DoesNotExist:
            return Response({"message": f"Render с id {render_id} не найден."}, status=404)

        if render_obj.Retoucher != request.user:
            return Response({"message": f"Render с id {render_id} не принадлежит вам."}, status=403)

        # Устанавливаем RetouchPhotosLink и фиксируем время завершения ретуши
        render_obj.RetouchPhotosLink = retouch_photos_link
        render_obj.RetouchTimeEnd = now
        render_obj.save()
        updated_ids.append(render_id)

    return Response({"message": "RetouchPhotosLink успешно обновлены."}, status=200)

#Отправить на проверку и завершить отклоненные
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def SendForCheck(request):
    user = request.user

    # 1. Обновляем все Render со статусом 5 в статус 7
    try:
        status7 = RetouchStatus.objects.get(id=7)
    except RetouchStatus.DoesNotExist:
        return Response({"message": "RetouchStatus с id=6 не найден."}, status=500)

    renders_status5 = Render.objects.filter(Retoucher=user, RetouchStatus__id=5)
    renders_status5.update(RetouchStatus=status7)

    # 2. Обработка Render со статусом 2:
    try:
        status3 = RetouchStatus.objects.get(id=3)
    except RetouchStatus.DoesNotExist:
        return Response({"message": "RetouchStatus с id=3 не найден."}, status=500)

    renders_status2 = Render.objects.filter(Retoucher=user, RetouchStatus__id=2)
    # Выбираем те, у которых заполнено поле RetouchPhotosLink (не Null и не пустая строка)
    renders_with_photos = renders_status2.exclude(Q(RetouchPhotosLink__isnull=True) | Q(RetouchPhotosLink=""))
    count_status3 = renders_with_photos.count()
    if count_status3:
        renders_with_photos.update(RetouchStatus=status3)

    # Проверяем, есть ли Render со статусом 2, у которых отсутствует ссылка
    renders_without_photos = renders_status2.filter(Q(RetouchPhotosLink__isnull=True) | Q(RetouchPhotosLink=""))
    missing_photos = renders_without_photos.exists()

    # 3. Отправляем сообщение в Telegram всем Старшим ретушерам, у которых on_work=True
    if count_status3 > 0: # <--- ВОТ ИЗМЕНЕНИЕ: Добавляем проверку
        senior_retouchers = User.objects.filter(
            groups__name="Старший ретушер",
            profile__on_work=True
        )
        retoucher_name = f"{user.first_name} {user.last_name}" if (user.first_name or user.last_name) else "Не указан"
        message_text = f"{retoucher_name} прислал на проверку {count_status3} рендеров"
        for senior in senior_retouchers:
            if hasattr(senior, 'profile') and senior.profile.telegram_id:
                async_task(
                    'telegram_bot.tasks.send_message_task',
                    chat_id=senior.profile.telegram_id,
                    text=message_text
                )

    # 4. Формируем ответ
    if missing_photos:
        return Response(
            {"message": "Не у всех штрихкодов стоят ссылки.", "status3_count": count_status3},
            status=200
        )
    else:
        return Response(
            {"message": "Отправлено на проверку.", "status3_count": count_status3},
            status=200
        )

#Получение листа правок у ретушера
class RetoucherRenderEditList(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RetoucherRenderSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Render.objects.filter(
            Retoucher=self.request.user,
            RetouchStatus__id__in=[4]
        )
        # Фильтрация по полю IsSuitable, если передан query параметр is_suitable
        is_suitable = self.request.query_params.get('is_suitable')
        if is_suitable is not None:
            if is_suitable.lower() in ['true', '1']:
                queryset = queryset.filter(IsSuitable=True)
            elif is_suitable.lower() in ['false', '0']:
                queryset = queryset.filter(IsSuitable=False)
        # Сортировка: новые в начале
        queryset = queryset.order_by('-created_at')
        # Оптимизация запросов
        queryset = queryset.select_related('Product', 'RetouchStatus').prefetch_related('CheckResult')
        return queryset

#проставить отклонено
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def SeniorUpdateRender(request, render_id):
    try:
        render_obj = Render.objects.get(pk=render_id)
    except Render.DoesNotExist:
        return Response({"message": "Не найдена запись."}, status=404)

    # Получаем данные из запроса
    check_result_ids = request.data.get("CheckResult")  # ожидается список id
    check_comment = request.data.get("CheckComment")
    is_suitable = request.data.get("IsSuitable")

    if is_suitable is None:
        return Response({"message": "Укажите, подходит ли шк для рендера."}, status=400)

    # Приводим is_suitable к булевому значению, если пришёл в виде строки
    if isinstance(is_suitable, str):
        if is_suitable.lower() in ['true', '1']:
            is_suitable = True
        elif is_suitable.lower() in ['false', '0']:
            is_suitable = False
        else:
            return Response({"message": "Неверное значение для пригодности на рендер."}, status=400)

    # Обновляем CheckComment, если передан
    if check_comment is not None:
        render_obj.CheckComment = check_comment

    # Обновляем IsSuitable
    render_obj.IsSuitable = is_suitable

    # Если IsSuitable=True, устанавливаем RetouchTimeStart = now
    if is_suitable:
        render_obj.RetouchTimeStart = timezone.now()

    # Устанавливаем RetouchStatus согласно значению IsSuitable
    new_status_id = 2 if is_suitable else 7
    try:
        retouch_status = RetouchStatus.objects.get(id=new_status_id)
    except RetouchStatus.DoesNotExist:
        return Response({"message": f"RetouchStatus with id={new_status_id} not found."}, status=500)
    render_obj.RetouchStatus = retouch_status

    render_obj.save()

    # Обновляем ManyToMany связь CheckResult, если передан список id
    if check_result_ids is not None:
        if not isinstance(check_result_ids, list):
            return Response({"message": "Результаты проверки должны быть списком ID."}, status=400)
        render_obj.CheckResult.set(check_result_ids)

    return Response({"message": "Запись успешно обновлена."}, status=200)

#получение списка ретушеров
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_retouchers_with_status3(request):
    # Выбираем пользователей, для которых есть хотя бы один Render с RetouchStatus.id == 3
    retouchers = User.objects.filter(render__RetouchStatus__id=3).distinct()
    
    # Формируем список с нужными данными
    data = [
        {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}".strip()
        }
        for user in retouchers
    ]
    
    return Response(data)

#Получение листа проверки у старшего
class SeniorRenderCheckList(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SeniorRenderSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Render.objects.filter(
            RetouchStatus__id__in=[3]
        )
        # Фильтрация по полю IsSuitable, если передан query параметр is_suitable
        is_suitable = self.request.query_params.get('is_suitable')
        if is_suitable is not None:
            if is_suitable.lower() in ['true', '1']:
                queryset = queryset.filter(IsSuitable=True)
            elif is_suitable.lower() in ['false', '0']:
                queryset = queryset.filter(IsSuitable=False)
        # Фильтрация по нескольким ретушерам, если передан query параметр retoucher
        retoucher_param = self.request.query_params.get('retoucher')
        if retoucher_param:
            try:
                retoucher_ids = [int(x.strip()) for x in retoucher_param.split(',') if x.strip()]
                queryset = queryset.filter(Retoucher_id__in=retoucher_ids)
            except ValueError:
                pass
        # Сортировка
        queryset = queryset.order_by('created_at')
        # Оптимизация запросов
        queryset = queryset.select_related('Product', 'RetouchStatus').prefetch_related('CheckResult')
        return queryset
    
#Проставка проверки у старшего
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def SeniorToEditRender(request):
    """
    Эндпоинт для массового обновления статуса рендера.
    Принимает в теле запроса:
      {
         "renders": [
           {"render_id": 20, "retouch_status_id": 6, "comment": ""},
           {"render_id": 24, "retouch_status_id": 4, "comment": "правки"},
           {"render_id": 27, "retouch_status_id": 6, "comment": ""}
         ]
      }
    Для каждого объекта:
      - Если retouch_status_id == 4, устанавливается SeniorRetouchStatus с id=2,
        если retouch_status_id == 6, то SeniorRetouchStatus с id=1.
      - Обновляется поле RetouchComment индивидуально.
    После обновления для рендеров со статусом 4 отправляется сообщение ретушеру,
    если у него указан telegram_id, с текстом "Правки по рендерам {кол-во}".
    """
    data = request.data
    renders_data = data.get("renders")

    # Проверяем, что пользователь принадлежит к группе "Старший ретушер"
    if not request.user.groups.filter(name="Старший ретушер").exists():
        return Response({"message": "У вас нет доступа к этой функции"}, status=403)
    
    if not isinstance(renders_data, list) or not renders_data:
        return Response({"message": "renders должен быть непустым массивом."}, status=400)
    
    updated_count = 0
    retoucher_counts = defaultdict(int)
    
    for render_info in renders_data:
        render_id = render_info.get("render_id")
        retouch_status_id = render_info.get("retouch_status_id")
        comment = render_info.get("comment", "")
        
        # Если render_id не передан, пропускаем этот элемент
        if render_id is None:
            continue
        
        if retouch_status_id not in [4, 6]:
            return Response({"message": "retouch_status_id должен быть равен 4 или 6."}, status=400)
        
        # Получаем новый статус ретуши
        try:
            new_status = RetouchStatus.objects.get(id=retouch_status_id)
        except RetouchStatus.DoesNotExist:
            return Response({"message": f"RetouchStatus с id {retouch_status_id} не найден."}, status=500)
        
        # Определяем соответствующий статус старшего ретушера:
        # Если retouch_status_id == 4, то senior_status_id = 2, иначе (если 6) = 1
        senior_status_id = 2 if retouch_status_id == 4 else 1
        try:
            new_senior_status = SeniorRetouchStatus.objects.get(id=senior_status_id)
        except SeniorRetouchStatus.DoesNotExist:
            return Response({"message": f"SeniorRetouchStatus с id {senior_status_id} не найден."}, status=500)
        
        # Получаем объект Render по render_id
        try:
            render_obj = Render.objects.get(id=render_id)
        except Render.DoesNotExist:
            continue  # Если рендер не найден, пропускаем
        
        # Обновляем поля для текущего рендера
        render_obj.RetouchStatus = new_status
        render_obj.RetouchSeniorComment = comment
        render_obj.RetouchSeniorStatus = new_senior_status
        render_obj.save()
        updated_count += 1
        
        # Если статус равен 4, учитываем для отправки сообщения ретушеру
        if retouch_status_id == 4 and render_obj.Retoucher:
            retoucher_counts[render_obj.Retoucher.id] += 1
    
    # Отправляем сообщения ретушерам для обновлённых рендеров со статусом 4
    for retoucher_id, count in retoucher_counts.items():
        try:
            retoucher = User.objects.get(id=retoucher_id)
        except User.DoesNotExist:
            continue
        if hasattr(retoucher, 'profile') and getattr(retoucher.profile, 'telegram_id', None):
            message_text = f"Правки по рендерам {count}"
            async_task(
                'telegram_bot.tasks.send_message_task',
                chat_id=retoucher.profile.telegram_id,
                text=message_text
            )
    
    return Response({"message": "Статус обновлён.", "updated_count": updated_count}, status=200)

#Получение нового задания на загрузку рендера модератором
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ModeratorUploadStart(request):
    moderator = request.user
    upload_status_in_progress_id = 1 # ID статуса "в работе" или "начато"

    # 1. Проверяем, есть ли уже активная задача у этого модератора
    # Используем select_related для оптимизации запроса к связанным моделям
    existing_upload = ModerationUpload.objects.filter(
        Moderator=moderator,
        UploadStatus__id=upload_status_in_progress_id
    ).select_related('RenderPhotos__Product').first()

    if existing_upload:
        # Если найдена активная задача, возвращаем её данные
        render = existing_upload.RenderPhotos
        data = {
            "ModerationUploadId": existing_upload.pk,
            "Barcode": render.Product.Barcode,
            "ProductID": render.Product.ProductID,
            "SKUID": render.Product.SKUID,
            "Name": render.Product.Name,
            "ShopID": render.Product.ShopID,
            "RetouchPhotosLink": render.RetouchPhotosLink,
        }
        return JsonResponse(data)

    # 2. Если активной задачи нет, ищем новую и создаем запись
    # Используем транзакцию для атомарности операции поиска и назначения
    try:
        with transaction.atomic():
            # Ищем следующий доступный рендер для загрузки
            # select_for_update() блокирует выбранные строки до конца транзакции
            render = Render.objects.select_for_update().filter(
                RetouchStatus__id=6,
                RetouchSeniorStatus__id=1,
                IsOnUpload=False,
                Product__IsModerationBlock=False
            ).select_related('Product').order_by("RetouchTimeEnd").first() # select_related для оптимизации

            # Если подходящего рендера не найдено, возвращаем сообщение
            if not render:
                return JsonResponse({"message": "Рендеры на загрузку закончились"}, status=404)

            # Получаем объект статуса "в работе"
            try:
                upload_status_started = UploadStatus.objects.get(id=upload_status_in_progress_id)
            except UploadStatus.DoesNotExist:
                # Это критическая ошибка конфигурации, если статус не найден
                # Логируйте эту ошибку!
                print(f"CRITICAL ERROR: UploadStatus with ID={upload_status_in_progress_id} not found!")
                return JsonResponse({"message": "Ошибка конфигурации: не найден статус загрузки."}, status=500)

            # Помечаем рендер как взятый в работу на загрузку
            render.IsOnUpload = True
            render.save()

            # Создаем новую запись ModerationUpload
            new_moderation_upload = ModerationUpload.objects.create(
                RenderPhotos=render,
                Moderator=moderator,
                UploadTimeStart=timezone.now(),
                UploadStatus=upload_status_started # <-- Устанавливаем статус "в работе"
            )

            # Формируем данные для ответа с информацией о новой задаче
            data = {
                "ModerationUploadId": new_moderation_upload.pk,
                "Barcode": render.Product.Barcode,
                "ProductID": render.Product.ProductID,
                "SKUID": render.Product.SKUID,
                "Name": render.Product.Name,
                "ShopID": render.Product.ShopID,
                "RetouchPhotosLink": render.RetouchPhotosLink,
            }
            return JsonResponse(data)

    except Exception as e:
        # Логируйте исключение для отладки
        print(f"Error during ModeratorUploadStart transaction: {e}") # Используйте logging в продакшене
        # Возвращаем общую ошибку пользователю
        return JsonResponse({"message": "Произошла ошибка при назначении задания."}, status=500)

#результат загрузки модератором
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ModerationUploadResult(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Неверный формат данных"}, status=400)

    moderation_upload_id = data.get("ModerationUploadId")
    if not moderation_upload_id:
        return JsonResponse({"error": "Не указан ModerationUploadId"}, status=400)

    moderation_upload = get_object_or_404(ModerationUpload, pk=moderation_upload_id)

    # Проверяем, что запрос делает пользователь, указанный в поле Moderator
    if moderation_upload.Moderator != request.user:
        return JsonResponse({"error": "Доступ запрещен"}, status=403)

    # Устанавливаем UploadTimeEnd равным текущему времени
    moderation_upload.UploadTimeEnd = timezone.now()

    # Обновляем UploadStatus в зависимости от поля IsUploaded
    is_uploaded = data.get("IsUploaded")
    if is_uploaded is True:
        # Предполагаем, что статус с id=2 означает "загружено"
        upload_status = UploadStatus.objects.filter(pk=2).first()
    else:
        # Предполагаем, что статус с id=3 означает "не загружено"
        upload_status = UploadStatus.objects.filter(pk=3).first()

    if not upload_status:
        return JsonResponse({"error": "UploadStatus не найден для данного статуса"}, status=400)

    moderation_upload.UploadStatus = upload_status
    moderation_upload.IsUploaded = is_uploaded

    # Обновляем остальные поля
    moderation_upload.IsRejected = data.get("IsRejected")
    moderation_upload.RejectComment = data.get("RejectComment")
    moderation_upload.ReturnToRender = data.get("ReturnToRender", False)  # По умолчанию False

    # Сохраняем объект, чтобы можно было обновить ManyToMany поле
    moderation_upload.save()

    # Если передан массив с ID отклоненных причин, обновляем RejectedReason
    rejected_reason_ids = data.get("RejectedReason")
    if isinstance(rejected_reason_ids, list):
        reasons = RejectedReason.objects.filter(pk__in=rejected_reason_ids)
        moderation_upload.RejectedReason.set(reasons)

    moderation_upload.save()

    return JsonResponse({"message": "Данные загружены успешно"})

#правка результата загрузки модератором
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ModerationUploadEdit(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Неверный формат данных"}, status=400)

    moderation_upload_id = data.get("ModerationUploadId")
    if not moderation_upload_id:
        return JsonResponse({"error": "Не указан ModerationUploadId"}, status=400)

    moderation_upload = get_object_or_404(ModerationUpload, pk=moderation_upload_id)

    # Проверяем, что запрос делает пользователь, указанный в поле Moderator
    if moderation_upload.Moderator != request.user:
        return JsonResponse({"error": "Доступ запрещен"}, status=403)

    from datetime import timedelta
    # Если UploadTimeEnd уже установлен, проверяем, не истёк ли срок редактирования
    if moderation_upload.UploadTimeEnd:
        if timezone.now() - moderation_upload.UploadTimeEnd > timedelta(minutes=60):
            return JsonResponse({"error": "истекло время редактирования"}, status=400)
    else:
        # Если UploadTimeEnd еще не установлен, устанавливаем его единожды
        moderation_upload.UploadTimeEnd = timezone.now()
        moderation_upload.save(update_fields=["UploadTimeEnd"])

    # Обновляем UploadStatus в зависимости от поля IsUploaded
    is_uploaded = data.get("IsUploaded")
    if is_uploaded is True:
        # Предполагаем, что статус с id=2 означает "загружено"
        upload_status = UploadStatus.objects.filter(pk=2).first()
    else:
        # Предполагаем, что статус с id=3 означает "не загружено"
        upload_status = UploadStatus.objects.filter(pk=3).first()

    if not upload_status:
        return JsonResponse({"error": "UploadStatus не найден для данного статуса"}, status=400)

    moderation_upload.UploadStatus = upload_status
    moderation_upload.IsUploaded = is_uploaded

    # Обновляем остальные поля
    moderation_upload.IsRejected = data.get("IsRejected")
    moderation_upload.RejectComment = data.get("RejectComment")
    moderation_upload.ReturnToRender = data.get("ReturnToRender", False)  # По умолчанию False

    moderation_upload.save()

    # Если передан массив с ID отклоненных причин, обновляем RejectedReason
    rejected_reason_ids = data.get("RejectedReason")
    if isinstance(rejected_reason_ids, list):
        reasons = RejectedReason.objects.filter(pk__in=rejected_reason_ids)
        moderation_upload.RejectedReason.set(reasons)

    moderation_upload.save()

    return JsonResponse({"message": "Данные загружены успешно"})

#Лист работы у модератора
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ModeratorListByDate(request, date_str=None):
    """
    Возвращает список ModerationUpload для текущего модератора, где UploadTimeStart 
    попадает в указанную дату (формат dd.mm.yyyy), а также статистику по количеству.
    Если дата не передана, используется текущий день.
    """
    if not date_str:
        query_date = timezone.localtime(timezone.now()).date()
    else:
        try:
            query_date = datetime.strptime(date_str, "%d.%m.%Y").date()
        except ValueError:
            return Response({"error": "Неверный формат даты, ожидалось dd.mm.yyyy"}, status=400)

    uploads_qs = ModerationUpload.objects.filter(
        Moderator=request.user,
        UploadTimeStart__date=query_date
    ).select_related('RenderPhotos__Product', 'UploadStatus') \
     .prefetch_related('RejectedReason') \
     .order_by('-pk')

    total_count = uploads_qs.count()
    uploaded_count = uploads_qs.filter(IsUploaded=True).count()

    uploads_qs = uploads_qs[:50]  # Ограничиваем только первыми 30 результатами
    uploads = list(uploads_qs)

    uploads_list = []
    for upload in uploads:
        upload_status = None
        if upload.UploadStatus:
            upload_status = {"id": upload.UploadStatus.id, "name": upload.UploadStatus.name}

        rejected_reasons = [{"id": reason.id, "name": reason.name} for reason in upload.RejectedReason.all()]

        UploadTimeStart = ""
        if upload.UploadTimeStart:
            local_time = timezone.localtime(upload.UploadTimeStart)
            UploadTimeStart = local_time.strftime("%d.%m.%Y %H:%M:%S")

        upload_data = {
            "ModerationUploadId": upload.pk,
            "Barcode": upload.RenderPhotos.Product.Barcode,
            "ProductID": upload.RenderPhotos.Product.ProductID,
            "SKUID": upload.RenderPhotos.Product.SKUID,
            "Name": upload.RenderPhotos.Product.Name,
            "ShopID": upload.RenderPhotos.Product.ShopID,
            "RetouchPhotosLink": upload.RenderPhotos.RetouchPhotosLink,
            "UploadStatus": upload_status,
            "UploadTimeStart": UploadTimeStart,
            "IsUploaded": upload.IsUploaded,
            "IsRejected": upload.IsRejected,
            "RejectedReason": rejected_reasons,
            "RejectComment": upload.RejectComment,
            "ReturnToRender": upload.ReturnToRender,
        }
        uploads_list.append(upload_data)

    response_data = {
        "uploads": uploads_list,
        "total_count": total_count,
        "uploaded_count": uploaded_count,
    }
    return Response(response_data)

#Статистика старшего модератора - вспомогательный вью
def process_upload_records(queryset, stats_dict):
    """
    Вспомогательная функция для обработки записей из queryset
    и обновления словаря статистики.
    """
    for record in queryset:
        # Пропускаем записи без времени начала загрузки, так как по нему идет фильтрация
        if not record.UploadTimeStart:
            continue

        # Приводим UploadTimeStart к локальному времени и извлекаем дату в требуемом формате
        # Используем timezone.localtime для корректного учета часовых поясов
        local_time = timezone.localtime(record.UploadTimeStart)
        date_key = local_time.strftime("%d.%m.%Y")

        moderator = record.Moderator
        # Формируем имя модератора или используем "Неизвестный", если модератор не назначен (null=True)
        moderator_name = f"{moderator.first_name} {moderator.last_name}".strip() if moderator else "Неизвестный"

        # Инициализируем вложенные словари, если их еще нет
        if date_key not in stats_dict:
            stats_dict[date_key] = {}
        if moderator_name not in stats_dict[date_key]:
            stats_dict[date_key][moderator_name] = {"total": 0, "Uploaded": 0, "Rejected": 0}

        # Обновляем счетчики
        stats_dict[date_key][moderator_name]["total"] += 1
        # Учитываем, что IsUploaded/IsRejected могут быть None, считаем только явные True
        if record.IsUploaded is True:
            stats_dict[date_key][moderator_name]["Uploaded"] += 1
        if record.IsRejected is True:
            stats_dict[date_key][moderator_name]["Rejected"] += 1

#Статистика старшего модератора - основной вью
@api_view(['GET'])
def SeniorModerationStats(request, date_from, date_to):
    """
    Эндпоинт для получения суммарной статистики по ModerationUpload и ModerationStudioUpload.
    Принимает два параметра в URL: date_from и date_to в формате dd.mm.yyyy.
    Считает записи с UploadTimeStart от date_from 00:00:00 до date_to 23:59:59.

    Для каждого дня и для каждого модератора (Moderator) формируется общая статистика:
      - total: общее количество записей (из обеих моделей)
      - Uploaded: количество записей, где IsUploaded=True (из обеих моделей)
      - Rejected: количество записей, где IsRejected=True (из обеих моделей)

    Имя модератора отправляется в формате "FirstName LastName".
    """
    try:
        start_date = datetime.strptime(date_from, "%d.%m.%Y").date()
        end_date = datetime.strptime(date_to, "%d.%m.%Y").date()
    except ValueError:
        return Response({"error": "Неверный формат даты, ожидалось dd.mm.yyyy"}, status=400)

    # Создаем границы диапазона: с начала первого дня до конца последнего дня
    # Используем timezone.make_aware для создания timezone-aware datetime объектов
    start_datetime = timezone.make_aware(datetime.combine(start_date, time.min)) # time.min = 00:00:00
    end_datetime = timezone.make_aware(datetime.combine(end_date, time.max)) # time.max = 23:59:59.999999

    # Структура для итоговой статистики
    # { "dd.mm.yyyy": { "FirstName LastName": {"total": N, "Uploaded": N, "Rejected": N}, ... }, ... }
    stats = {}

    # 1. Получаем и обрабатываем данные из ModerationUpload
    moderation_uploads = ModerationUpload.objects.filter(
        UploadTimeStart__gte=start_datetime,
        UploadTimeStart__lte=end_datetime
    ).select_related('Moderator') # Оптимизация запроса к связанной модели User
    process_upload_records(moderation_uploads, stats)

    # 2. Получаем и обрабатываем данные из ModerationStudioUpload
    studio_uploads = ModerationStudioUpload.objects.filter(
        UploadTimeStart__gte=start_datetime,
        UploadTimeStart__lte=end_datetime
    ).select_related('Moderator') # Оптимизация запроса к связанной модели User
    process_upload_records(studio_uploads, stats) # Используем ту же функцию и тот же словарь stats

    # Возвращаем объединенную статистику
    return Response(stats)

#Статистика ретушеров для старшего
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def SeniorRetoucherStats(request, date_from, date_to):
    """
    Эндпоинт для получения статистики Render по ретушерам за заданный период.
    
    Параметры URL:
      date_from - начало периода (формат dd.mm.yyyy, время 00:00:00)
      date_to - конец периода (формат dd.mm.yyyy, время 23:59:59)
    
    Рассматриваются Render, у которых:
      - CheckTimeStart входит в указанный диапазон
      - RetouchStatus имеет id равное 6 или 7

    Статистика для каждого ретушера (Retoucher, формат "FirstName LastName"):
      - total: общее количество Render
      - Processed: количество Render со статусом 6 (обработанные)
      - Rejected: количество Render со статусом 7 (отклоненные)
      
    Группировка происходит по датам (из поля CheckTimeStart) с форматированием dd.mm.yyyy.
    """
    try:
        start_date = datetime.strptime(date_from, "%d.%m.%Y").date()
        end_date = datetime.strptime(date_to, "%d.%m.%Y").date()
    except ValueError:
        return Response({"error": "Неверный формат даты, ожидалось dd.mm.yyyy"}, status=400)

    # Формируем границы периода
    start_datetime = timezone.make_aware(datetime.combine(start_date, time(0, 0, 0)))
    end_datetime = timezone.make_aware(datetime.combine(end_date, time(23, 59, 59)))

    # Фильтруем Render по дате CheckTimeStart и RetouchStatus (6 или 7)
    renders = Render.objects.filter(
        CheckTimeStart__gte=start_datetime,
        CheckTimeStart__lte=end_datetime,
        RetouchStatus__id__in=[6, 7]
    ).select_related('Retoucher', 'RetouchStatus')

    stats = {}
    for render in renders:
        if not render.CheckTimeStart:
            continue
        # Приводим время к локальному и извлекаем дату
        local_time = timezone.localtime(render.CheckTimeStart)
        date_key = local_time.strftime("%d.%m.%Y")

        retoucher = render.Retoucher
        retoucher_name = f"{retoucher.first_name} {retoucher.last_name}".strip() if retoucher else "Неизвестный"

        if date_key not in stats:
            stats[date_key] = {}
        if retoucher_name not in stats[date_key]:
            stats[date_key][retoucher_name] = {"total": 0, "Processed": 0, "Rejected": 0}

        stats[date_key][retoucher_name]["total"] += 1
        if render.RetouchStatus and render.RetouchStatus.id == 6:
            stats[date_key][retoucher_name]["Processed"] += 1
        elif render.RetouchStatus and render.RetouchStatus.id == 7:
            stats[date_key][retoucher_name]["Rejected"] += 1

    return Response(stats)

#Просмотр возвращенных на рендер
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def SeniorReturnToRenderList(request):
    """
    Возвращает список ModerationUpload, у которых:
      - ReturnToRender = True
      - ReturnToRenderComplete = False
    Данные включают:
      - ModerationUpload.pk
      - Moderator (в формате "FirstName LastName")
      - UploadTimeStart (отформатирован с учетом локального времени, "dd.mm.yyyy hh:mm:ss")
      - RejectedReason – массив объектов с полями id и name
      - RejectComment
      - Render (id, Retoucher, RetouchTimeEnd, RetouchPhotosLink)
      - Product (Barcode, ProductID, SKUID, Name, ShopID)
    Записи сортируются по UploadTimeEnd (сначала старые).
    Для оптимизации используется select_related и prefetch_related.
    """
    uploads = ModerationUpload.objects.filter(
        ReturnToRender=True,
        ReturnToRenderComplete=False
    ).select_related(
        'Moderator',
        'RenderPhotos',
        'RenderPhotos__Product',
        'RenderPhotos__Retoucher'
    ).prefetch_related('RejectedReason').order_by('UploadTimeEnd')

    result = []
    for upload in uploads:
        moderator = upload.Moderator
        moderator_name = f"{moderator.first_name} {moderator.last_name}".strip() if moderator else "Неизвестный"
        
        upload_time_start = ""
        if upload.UploadTimeStart:
            local_upload_time = timezone.localtime(upload.UploadTimeStart)
            upload_time_start = local_upload_time.strftime("%d.%m.%Y %H:%M:%S")
        
        # Сериализация RejectedReason
        rejected_reasons = [{"id": reason.id, "name": reason.name} for reason in upload.RejectedReason.all()]
        
        # Данные Render (RenderPhotos)
        render = upload.RenderPhotos
        render_id = render.pk if render else None
        
        retoucher = render.Retoucher if render and render.Retoucher else None
        retoucher_name = f"{retoucher.first_name} {retoucher.last_name}".strip() if retoucher else "Неизвестный"
        
        render_retouch_time_end = ""
        if render and render.RetouchTimeEnd:
            local_retouch_time = timezone.localtime(render.RetouchTimeEnd)
            render_retouch_time_end = local_retouch_time.strftime("%d.%m.%Y %H:%M:%S")
        
        render_photos_link = render.RetouchPhotosLink if render else ""
        
        # Данные продукта
        product = render.Product if render and hasattr(render, 'Product') else None
        product_barcode = product.Barcode if product else ""
        product_id = product.ProductID if product else None
        product_skuid = product.SKUID if product else None
        product_name = product.Name if product else ""
        product_shop_id = product.ShopID if product else None
        
        result.append({
            "ModerationUploadId": upload.pk,
            "Moderator": moderator_name,
            "UploadTimeStart": UploadTimeStart,
            "RejectedReason": rejected_reasons,
            "RejectComment": upload.RejectComment,
            "RenderId": render_id,
            "RenderRetoucher": retoucher_name,
            "RenderRetouchTimeEnd": render_retouch_time_end,
            "RenderRetouchPhotosLink": render_photos_link,
            "ProductBarcode": product_barcode,
            "ProductID": product_id,
            "ProductSKUID": product_skuid,
            "ProductName": product_name,
            "ProductShopID": product_shop_id,
        })

    return Response(result)

#старт загрузки стуйдийных фото
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ModerationStudioUploadStart(request):

    user = request.user

    # 1. Проверяем группу "Moderator"
    if not user.groups.filter(name="Moderator").exists():
        return Response({"detail": "Access denied. Not a Moderator."},
                        status=status.HTTP_403_FORBIDDEN)

    # 2. Проверяем существующую загрузку
    existing_upload = ModerationStudioUpload.objects.select_related(
        'RenderPhotos__st_request_product__product',
        'UploadStatus'
    ).filter(Moderator=user, UploadStatus__id=1).first()

    if existing_upload:
        retouch = existing_upload.RenderPhotos
    else:
        # 3. Ищем новую ретушь
        retouch = RetouchRequestProduct.objects.select_related(
            'st_request_product__product'
        ).filter(
            IsOnUpload=False,
            retouch_status__id=2,
            sretouch_status__id=1
        ).order_by('updated_at').first()

        if not retouch:
            return Response({"detail": "закончились шк для загрузки"},
                            status=status.HTTP_404_NOT_FOUND)

        retouch.IsOnUpload = True
        retouch.save()

        existing_upload = ModerationStudioUpload.objects.create(
            RenderPhotos=retouch,
            Moderator=user,
            UploadTimeStart=timezone.now(),
            UploadStatus=UploadStatus.objects.get(id=1)
        )

    # Получаем штрихкод
    try:
        barcode = retouch.st_request_product.product.barcode
    except AttributeError:
         if not existing_upload.RenderPhotos == retouch:
             retouch.IsOnUpload = False
             retouch.save()
             existing_upload.delete()
         return Response({"detail": "Ошибка получения данных продукта из ретуши."}, status=status.HTTP_400_BAD_REQUEST)

    # Ищем продукт
    try:
        product_info = Product.objects.get(Barcode=barcode)
    except Product.DoesNotExist:
        if not existing_upload.RenderPhotos == retouch:
             retouch.IsOnUpload = False
             retouch.save()
             existing_upload.delete()
        return Response({"detail": f"Product with barcode {barcode} not found in Render DB"},
                        status=status.HTTP_404_NOT_FOUND)

    # Формируем ответ
    response_data = {
        "ModerationStudioUploadId": existing_upload.pk,
        "Barcode": barcode,
        "ProductID": product_info.ProductID,
        "SKUID": product_info.SKUID,
        "Name": product_info.Name,
        "ShopID": product_info.ShopID,
        "RetouchPhotosLink": getattr(retouch, 'retouch_link', '')
    }
    # Используем DRF Response для единообразия
    return Response(response_data, status=status.HTTP_200_OK)

#Результат загрузки студийного
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ModerationStudioUploadResult(request):
    """
    Обрабатывает результат загрузки модератором для модели ModerationStudioUpload.
    Принимает JSON с ModerationStudioUploadId и данными о результате модерации.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Неверный формат данных (ожидается JSON)"}, status=400)

    # --- Изменено: Используем ModerationStudioUploadId ---
    moderation_studio_upload_id = data.get("ModerationStudioUploadId")
    if not moderation_studio_upload_id:
        # --- Изменено: Обновлено сообщение об ошибке ---
        return JsonResponse({"error": "Не указан ModerationStudioUploadId"}, status=400)

    # --- Изменено: Используем модель ModerationStudioUpload ---
    moderation_studio_upload = get_object_or_404(ModerationStudioUpload, pk=moderation_studio_upload_id)

    # Проверяем, что запрос делает пользователь, указанный в поле Moderator
    # (Убедитесь, что поле Moderator установлено перед вызовом этого эндпоинта)
    if moderation_studio_upload.Moderator != request.user:
        return JsonResponse({"error": "Доступ запрещен. Запрос может сделать только назначенный модератор."}, status=403)

    # Устанавливаем UploadTimeEnd равным текущему времени
    # (Модель ModerationStudioUpload автоматически вычислит UploadTime при сохранении)
    moderation_studio_upload.UploadTimeEnd = timezone.now()

    # Обновляем UploadStatus в зависимости от поля IsUploaded
    is_uploaded = data.get("IsUploaded")
    if is_uploaded is None: # Добавлена проверка на None
         return JsonResponse({"error": "Не указан статус IsUploaded (true/false)"}, status=400)

    # Убедитесь, что эти ID соответствуют вашей модели UploadStatus
    if is_uploaded is True:
        # Статус "загружено" (предполагаем ID=2)
        upload_status = UploadStatus.objects.filter(pk=2).first()
        if not upload_status:
            return JsonResponse({"error": "Статус загрузки (UploadStatus) с ID=2 не найден в базе данных."}, status=400) # Улучшено сообщение

        try:
            operation_type_uploaded = ProductOperationTypes.objects.get(pk=58)

            render_photos_instance = moderation_studio_upload.RenderPhotos
            if not render_photos_instance:
                 return JsonResponse({"error": "Связанный объект RenderPhotos отсутствует у ModerationStudioUpload."}, status=400)

            st_request_product_instance = render_photos_instance.st_request_product
            if not st_request_product_instance:
                 return JsonResponse({"error": "Связанный объект st_request_product отсутствует у RenderPhotos."}, status=400)
            
            product_instance = st_request_product_instance.product
            if not product_instance:
                return JsonResponse({"error": "Связанный объект Product отсутствует у STRequestProduct."}, status=400)
            
            comment_text = render_photos_instance.retouch_link

            product_op = ProductOperation.objects.create(
                product=product_instance,
                operation_type=operation_type_uploaded,
                user=request.user,
                comment=comment_text
            )
        except ProductOperationTypes.DoesNotExist:
            return JsonResponse({"error": "Тип операции ProductOperationTypes с ID=58 не найден."}, status=500)
        except AttributeError as e:
            return JsonResponse({"error": f"Ошибка при доступе к связанным данным для создания ProductOperation: {e}"}, status=500)
        except Exception as e:
            return JsonResponse({"error": f"Непредвиденная ошибка при создании записи ProductOperation: {e}"}, status=500)
        # --- КОНЕЦ ЛОГИРОВАНИЯ ДЛЯ ProductOperation ---
    else:
        # Статус "не загружено" (предполагаем ID=3)
        upload_status = UploadStatus.objects.filter(pk=3).first()

    if not upload_status:
        # Улучшено сообщение об ошибке
        status_id = 2 if is_uploaded else 3
        return JsonResponse({"error": f"Статус загрузки (UploadStatus) с ID={status_id} не найден в базе данных."}, status=400)

    moderation_studio_upload.UploadStatus = upload_status
    moderation_studio_upload.IsUploaded = is_uploaded

    # Обновляем остальные поля (IsRejected, RejectComment, ReturnToRender)
    # Убедитесь, что ключи в data соответствуют ожидаемым
    is_rejected = data.get("IsRejected")
    if is_rejected is None: # Добавлена проверка на None
        return JsonResponse({"error": "Не указан статус IsRejected (true/false)"}, status=400)

    moderation_studio_upload.IsRejected = is_rejected
    moderation_studio_upload.RejectComment = data.get("RejectComment", "") # По умолчанию пустая строка, если не передано

    # Если отклонено (IsRejected=True), RejectComment и RejectedReason должны быть предоставлены (добавлена логика)
    rejected_reason_ids = data.get("RejectedReason", []) # По умолчанию пустой список
    if is_rejected:
        if not rejected_reason_ids or not isinstance(rejected_reason_ids, list):
            return JsonResponse({"error": "Поле RejectedReason (список ID причин) обязательно при отклонении (IsRejected=true)"}, status=400)

    moderation_studio_upload.ReturnToRender = data.get("ReturnToRender", False) # По умолчанию False

    # Сохраняем объект перед обработкой ManyToMany
    moderation_studio_upload.save()

    # Если IsRejected=True и передан массив с ID отклоненных причин, обновляем StudioRejectedReason
    if is_rejected and isinstance(rejected_reason_ids, list):
        # --- Изменено: Используем модель StudioRejectedReason ---
        reasons = StudioRejectedReason.objects.filter(pk__in=rejected_reason_ids)
        if len(reasons) != len(rejected_reason_ids):
            # Проверка, что все переданные ID существуют
            found_ids = {r.pk for r in reasons}
            missing_ids = [rid for rid in rejected_reason_ids if rid not in found_ids]
            return JsonResponse({"error": f"Не найдены причины отклонения (StudioRejectedReason) с ID: {missing_ids}"}, status=400)
        moderation_studio_upload.RejectedReason.set(reasons)
    elif not is_rejected:
        # Если не отклонено, очищаем причины отклонения
        moderation_studio_upload.RejectedReason.clear()
    # Если IsRejected=True, но rejected_reason_ids пустой или не список, ошибка уже была возвращена выше

    # Финальное сохранение (не обязательно, если нет изменений после .set(), но для ясности можно оставить)
    # moderation_studio_upload.save() # Модель уже сохранена выше, и .set() обновляет M2M сразу

    return JsonResponse({"message": "Данные успешно сохранены"})

#лист загрузки студийных
class ModerationStudioUploadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        # 1. Проверка, что пользователь состоит в группе "Moderator"
        if not user.groups.filter(name="Moderator").exists():
            return Response({"detail": "Access denied. Not a Moderator."},
                            status=status.HTTP_403_FORBIDDEN)

        # 2. Базовый QuerySet для записей текущего пользователя за сегодня
        base_queryset = ModerationStudioUpload.objects.filter(
            Moderator=user,
            UploadTimeStart__date=today
        )

        # 3. Расчет total_count (статусы 2 и 3)
        # Предполагаем, что ID статусов "Загружено" и "Обработано" (или аналогичные) это 2 и 3.
        # Уточните ID, если они другие!
        total_count = base_queryset.filter(
            UploadStatus__id__in=[2, 3] # Используем __in для нескольких ID
        ).count()

        # 4. Расчет uploaded_count (статус 3)
        # Предполагаем, что ID статуса "Загружено" (или конечного успешного) это 3.
        # Уточните ID, если он другой!
        uploaded_count = base_queryset.filter(
            UploadStatus__id=2
        ).count()

        # 5. Получаем последние 30 записей для списка (как и раньше)
        # Используем тот же базовый queryset, чтобы не повторять фильтры
        uploads_for_list = base_queryset.select_related(
            'UploadStatus',
            # Обратите внимание на глубину связи для product.barcode
            'RenderPhotos__st_request_product__product'
        ).prefetch_related(
            'RejectedReason'
        ).order_by('-pk')[:50]

        # 6. Формируем список результатов (как и раньше)
        formatted_uploads_list = []
        for upload in uploads_for_list:
            product = None
            barcode = None
            product_info = None

            # Извлекаем продукт и штрихкод более безопасно
            try:
                # Проверяем цепочку связей перед доступом
                if upload.RenderPhotos and \
                   upload.RenderPhotos.st_request_product and \
                   upload.RenderPhotos.st_request_product.product:
                    product = upload.RenderPhotos.st_request_product.product
                    barcode = product.barcode
            except AttributeError: # Ловим ошибку, если какой-то объект в цепочке None
                 barcode = None
                 product = None # Убедимся что product тоже None

            # Ищем Product (Render) по штрихкоду, если он есть
            # (Это отдельный запрос к другой модели, возможно стоит пересмотреть)
            # Если ProductID, SKUID и т.д. есть в той же модели что и barcode, этот запрос не нужен
            if barcode:
                try:
                    # Если ProductID, Name и т.д. уже есть в `product` из предыдущего шага,
                    # то используйте его: product_info = product
                    # Иначе, если это ДРУГАЯ модель Product, то ищем:
                    product_info = Product.objects.filter(Barcode=barcode).first() # Используем first() для избежания ошибки DoesNotExist
                except Exception as e: # Лучше ловить конкретные исключения, если возможно
                    print(f"Error fetching Product by barcode {barcode}: {e}") # Логирование ошибки
                    product_info = None

            # Формируем вложенный массив для UploadStatus
            upload_status_list = []
            if upload.UploadStatus:
                upload_status_list = [{"id": upload.UploadStatus.id, "name": upload.UploadStatus.name}]

            # Формируем вложенный массив для RejectedReason
            rejected_reason_list = [
                {"id": reason.id, "name": reason.name}
                for reason in upload.RejectedReason.all()
            ]

            # Форматируем UploadTimeStart
            upload_time_start_str = ""
            if upload.UploadTimeStart:
                upload_time_start_str = upload.UploadTimeStart.strftime("%d.%m.%y %H:%M:%S")

            formatted_uploads_list.append({
                "ModerationStudioUploadId": upload.pk,
                "Barcode": barcode,
                # Безопасный доступ к атрибутам product_info
                "ProductID": getattr(product_info, 'ProductID', None),
                "SKUID": getattr(product_info, 'SKUID', None),
                "Name": getattr(product_info, 'Name', None),
                "ShopID": getattr(product_info, 'ShopID', None),
                # Безопасный доступ к retouch_link
                "RetouchPhotosLink": getattr(upload.RenderPhotos, 'retouch_link', None),
                "UploadStatus": upload_status_list,
                "UploadTimeStart": upload_time_start_str,
                "IsUploaded": upload.IsUploaded,
                "IsRejected": upload.IsRejected,
                "RejectedReason": rejected_reason_list,
                "RejectComment": upload.RejectComment,
            })

        # 7. Формируем финальный ответ в требуемом формате
        response_data = {
            "uploads": formatted_uploads_list,
            "total_count": total_count,
            "uploaded_count": uploaded_count,
        }

        return Response(response_data, status=status.HTTP_200_OK)

#Правка загрузки студии
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ModerationStudioUploadEdit(request):
    """
    Эндпоинт для РЕДАКТИРОВАНИЯ результата загрузки модератором
    для модели ModerationStudioUpload.
    Позволяет модератору изменить свое решение в течение 60 минут
    после первоначальной установки UploadTimeEnd.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Неверный формат данных (ожидается JSON)"}, status=400)

    # --- Изменено: Используем ModerationStudioUploadId ---
    moderation_studio_upload_id = data.get("ModerationStudioUploadId")
    if not moderation_studio_upload_id:
        # --- Изменено: Обновлено сообщение об ошибке ---
        return JsonResponse({"error": "Не указан ModerationStudioUploadId"}, status=400)

    # --- Изменено: Используем модель ModerationStudioUpload ---
    moderation_studio_upload = get_object_or_404(ModerationStudioUpload, pk=moderation_studio_upload_id)

    # Проверяем, что запрос делает пользователь, указанный в поле Moderator
    if moderation_studio_upload.Moderator != request.user:
        return JsonResponse({"error": "Доступ запрещен. Редактировать может только назначенный модератор."}, status=403)

    # Проверка времени редактирования:
    # Проверяем, не истёк ли срок редактирования (60 минут)
    if timezone.now() - moderation_studio_upload.UploadTimeStart > timedelta(minutes=60):
        return JsonResponse({"error": "Время редактирования (60 минут) истекло."}, status=400)

    # --- Начало блока обновления данных ---

    # Обновляем UploadStatus в зависимости от поля IsUploaded
    is_uploaded = data.get("IsUploaded")
    if is_uploaded is None: # Добавлена проверка на None
         return JsonResponse({"error": "Не указан статус IsUploaded (true/false)"}, status=400)

    # Предполагаем те же ID для статусов загрузки, что и в оригинальном эндпоинте
    if is_uploaded is True:
        # Статус "загружено" (предполагаем ID=2)
        upload_status = UploadStatus.objects.filter(pk=2).first()
        try:
            operation_type_uploaded = ProductOperationTypes.objects.get(pk=58)

            render_photos_instance = moderation_studio_upload.RenderPhotos
            if not render_photos_instance:
                 return JsonResponse({"error": "Связанный объект RenderPhotos отсутствует у ModerationStudioUpload."}, status=400)

            st_request_product_instance = render_photos_instance.st_request_product
            if not st_request_product_instance:
                 return JsonResponse({"error": "Связанный объект st_request_product отсутствует у RenderPhotos."}, status=400)
            
            product_instance = st_request_product_instance.product
            if not product_instance:
                return JsonResponse({"error": "Связанный объект Product отсутствует у STRequestProduct."}, status=400)
            
            comment_text = render_photos_instance.retouch_link

            product_op = ProductOperation.objects.create(
                product=product_instance,
                operation_type=operation_type_uploaded,
                user=request.user,
                comment=comment_text
            )
        except ProductOperationTypes.DoesNotExist:
            return JsonResponse({"error": "Тип операции ProductOperationTypes с ID=58 не найден."}, status=500)
        except AttributeError as e:
            return JsonResponse({"error": f"Ошибка при доступе к связанным данным для создания ProductOperation: {e}"}, status=500)
        except Exception as e:
            return JsonResponse({"error": f"Непредвиденная ошибка при создании записи ProductOperation: {e}"}, status=500)
        # --- КОНЕЦ ЛОГИРОВАНИЯ ДЛЯ ProductOperation ---
    else:
        # Статус "не загружено" (предполагаем ID=3)
        upload_status = UploadStatus.objects.filter(pk=3).first()

    if not upload_status:
        status_id = 2 if is_uploaded else 3
        return JsonResponse({"error": f"Статус загрузки (UploadStatus) с ID={status_id} не найден в базе данных."}, status=400)

    moderation_studio_upload.UploadStatus = upload_status
    moderation_studio_upload.IsUploaded = is_uploaded

    # Обновляем остальные поля (IsRejected, RejectComment, ReturnToRender)
    is_rejected = data.get("IsRejected")
    if is_rejected is None: # Добавлена проверка на None
        return JsonResponse({"error": "Не указан статус IsRejected (true/false)"}, status=400)

    moderation_studio_upload.IsRejected = is_rejected
    moderation_studio_upload.RejectComment = data.get("RejectComment", "") # По умолчанию пустая строка

    # Валидация для случая отклонения (IsRejected=True)
    rejected_reason_ids = data.get("RejectedReason", []) # По умолчанию пустой список
    if is_rejected:
        if not moderation_studio_upload.RejectComment:
             return JsonResponse({"error": "Поле RejectComment обязательно при отклонении (IsRejected=true)"}, status=400)
        if not rejected_reason_ids or not isinstance(rejected_reason_ids, list):
            return JsonResponse({"error": "Поле RejectedReason (список ID причин) обязательно при отклонении (IsRejected=true)"}, status=400)

    moderation_studio_upload.ReturnToRender = data.get("ReturnToRender", False) # По умолчанию False

    # Сохраняем основные изменения перед обработкой ManyToMany
    # Обратите внимание: UploadTimeEnd НЕ обновляется при редактировании
    moderation_studio_upload.save(update_fields=[
        'UploadStatus', 'IsUploaded', 'IsRejected',
        'RejectComment', 'ReturnToRender', 'updated_at'
    ])

    # Обновляем поле ManyToMany RejectedReason
    if isinstance(rejected_reason_ids, list):
        if is_rejected:
            # --- Изменено: Используем модель StudioRejectedReason ---
            reasons = StudioRejectedReason.objects.filter(pk__in=rejected_reason_ids)
            if len(reasons) != len(set(rejected_reason_ids)): # Используем set для уникальных ID
                # Проверка, что все переданные уникальные ID существуют
                found_ids = {r.pk for r in reasons}
                missing_ids = list(set(rejected_reason_ids) - found_ids)
                return JsonResponse({"error": f"Не найдены причины отклонения (StudioRejectedReason) с ID: {missing_ids}"}, status=400)
            moderation_studio_upload.RejectedReason.set(reasons)
        else:
             # Если IsRejected=False, очищаем причины
            moderation_studio_upload.RejectedReason.clear()
    # Если rejected_reason_ids не список (и IsRejected=True), ошибка уже была возвращена выше

    # Финальное сохранение не требуется, т.к. .set() и .clear() выполняют свои SQL-запросы

    return JsonResponse({"message": "Данные модерации успешно отредактированы"})

#Моя статистика по загрузкам
class MyUploadStatView(APIView):
    permission_classes = [IsAuthenticated, IsModeratorUser] # Требуем аутентификацию и проверку группы

    def get(self, request, date_from, date_to):
        # 1. Парсинг и валидация дат
        try:
            date_format = "%d.%m.%Y"
            start_date = datetime.strptime(date_from, date_format).date()
            end_date = datetime.strptime(date_to, date_format).date()
        except ValueError:
            return Response(
                {"error": "Неверный формат даты. Используйте ДД.ММ.ГГГГ."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка, что дата начала не позже даты окончания
        if start_date > end_date:
            return Response(
                {"error": "Дата начала не может быть позже даты окончания."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Определение временного диапазона для запроса
        # Устанавливаем время на начало дня для date_from
        start_datetime = datetime.combine(start_date, time.min)
        # Устанавливаем время на конец дня для date_to (добавляем 1 день и берем начало дня)
        end_datetime = datetime.combine(end_date + timedelta(days=1), time.min)

        # Важно: Учет таймзон, если USE_TZ=True в settings.py
        if timezone.is_aware(timezone.now()): # Проверяем, используются ли таймзоны
             # Преобразуем наивные datetime в aware datetime, используя текущую таймзону
             # Или можно использовать settings.TIME_ZONE
             current_tz = timezone.get_current_timezone()
             start_datetime = timezone.make_aware(start_datetime, current_tz)
             end_datetime = timezone.make_aware(end_datetime, current_tz)
             # Если UploadTimeStart хранится в UTC, возможно, понадобится конвертация
             # start_datetime = start_datetime.astimezone(timezone.utc)
             # end_datetime = end_datetime.astimezone(timezone.utc)


        # 3. Получение текущего пользователя (модератора)
        moderator = request.user

        # 4. Запрос к базе данных для первой модели (ModerationUpload)
        stats1 = ModerationUpload.objects.filter(
            Moderator=moderator,
            UploadTimeStart__gte=start_datetime,
            UploadTimeStart__lt=end_datetime, # Используем __lt для < end_datetime
            UploadStatus__isnull=False # Исключаем записи без статуса
        ).annotate(
            day=TruncDate('UploadTimeStart') # Группируем по дате (без времени)
        ).values('day').annotate(
            uploaded=Count('id', filter=Q(UploadStatus_id=2)), # Статус "Загружено" = 2
            rejected=Count('id', filter=Q(UploadStatus_id=3))  # Статус "Отклонено" = 3
        ).values('day', 'uploaded', 'rejected').order_by('day') # Явно запрашиваем нужные поля


        # 5. Запрос к базе данных для второй модели (ModerationStudioUpload)
        stats2 = ModerationStudioUpload.objects.filter(
            Moderator=moderator,
            UploadTimeStart__gte=start_datetime,
            UploadTimeStart__lt=end_datetime, # Используем __lt для < end_datetime
            UploadStatus__isnull=False # Исключаем записи без статуса
        ).annotate(
            day=TruncDate('UploadTimeStart') # Группируем по дате (без времени)
        ).values('day').annotate(
            uploaded=Count('id', filter=Q(UploadStatus_id=2)), # Статус "Загружено" = 2
            rejected=Count('id', filter=Q(UploadStatus_id=3))  # Статус "Отклонено" = 3
        ).values('day', 'uploaded', 'rejected').order_by('day') # Явно запрашиваем нужные поля

        # 6. Объединение результатов и форматирование вывода
        combined_stats = {}
        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime(date_format)
            combined_stats[day_str] = {"Загружено": 0, "Отклонено": 0}
            current_date += timedelta(days=1)

        # Суммируем статистику из первого запроса
        for stat in stats1:
            day_key = stat['day'].strftime(date_format)
            if day_key in combined_stats: # Убедимся, что день в запрошенном диапазоне
                combined_stats[day_key]["Загружено"] += stat['uploaded']
                combined_stats[day_key]["Отклонено"] += stat['rejected']

        # Суммируем статистику из второго запроса
        for stat in stats2:
            day_key = stat['day'].strftime(date_format)
            if day_key in combined_stats: # Убедимся, что день в запрошенном диапазоне
                combined_stats[day_key]["Загружено"] += stat['uploaded']
                combined_stats[day_key]["Отклонено"] += stat['rejected']


        # 7. Возвращаем результат
        return Response(combined_stats, status=status.HTTP_200_OK)

#работа с отклоненными рендерами на этапе загрузки
class ModerationUploadRejectToRetouch(generics.ListAPIView):
    """
    API эндпоинт для получения списка ModerationUpload, отклоненных
    по определенным причинам и ожидающих возврата ретушерам.
    """
    serializer_class = ModerationUploadRejectSerializer
    pagination_class = StandardResultsSetPagination # Подключаем пагинацию
    # filter_backends = [OrderingFilter] # Опционально, если нужна гибкая сортировка
    # ordering_fields = ['UploadTimeStart', 'RenderPhotos__Product__Barcode'] # Поля для возможной сортировки

    def get_queryset(self):
        """
        Переопределяем метод для получения отфильтрованного и отсортированного queryset.
        """
        # Список ID причин отклонения
        reject_reason_ids = [1, 2, 4, 5, 7, 9]

        # Фильтруем ModerationUpload
        queryset = ModerationUpload.objects.filter(
            RejectedReason__id__in=reject_reason_ids, # Причины отклонения из списка
            ReturnToRenderComplete=False            # Еще не забраны ретушерами
        ).distinct() # Используем distinct из-за фильтрации по ManyToMany

        # Оптимизация запросов к базе данных
        queryset = queryset.select_related(
            'RenderPhotos',
            'RenderPhotos__Product',
            'RenderPhotos__Retoucher' # 'RenderPhotos__Retoucher' это User
        ).prefetch_related(
            'RejectedReason' # Для ManyToMany поля RejectedReason
        )

        # Сортировка по умолчанию
        queryset = queryset.order_by('UploadTimeStart') # Сначала более ранние

        return queryset

#работа с отклоненными - отправить на правки
class SendModerationUploadForEdits(APIView):
    """
    Эндпоинт для отправки ModerationUpload на правки ретушеру.
    Обновляет ReturnToRenderComplete = True.
    Метод: POST
    URL: /rd/moderation-uploads/{pk}/send-for-edits/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        moderation_upload = get_object_or_404(ModerationUpload, pk=pk)
        render_instance = moderation_upload.RenderPhotos

        if not render_instance:
            return Response({"detail": "Связанный объект Render не найден."}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.now().date()
        # Убрал подробности даты из сообщения об ошибке по вашему исходному коду
        if not render_instance.RetouchTimeEnd or render_instance.RetouchTimeEnd.date() != today:
             raise ValidationError(f"Прошло время отправки на правку. Отправка возможна только в день окончания ретуши.")


        try:
            with transaction.atomic():
                retouch_status_4 = get_object_or_404(RetouchStatus, pk=4)
                senior_status_2 = get_object_or_404(SeniorRetouchStatus, pk=2)

                # Обновляем Render
                render_instance.RetouchStatus = retouch_status_4
                render_instance.RetouchSeniorStatus = senior_status_2
                render_instance.IsOnUpload = False
                render_instance.save()

                # Обновляем ModerationUpload
                moderation_upload.ReturnToRenderComplete = True
                moderation_upload.save()

            # --- БЛОК ОТПРАВКИ УВЕДОМЛЕНИЯ (ВНЕ ТРАНЗАКЦИИ) ---
            retoucher = render_instance.Retoucher
            if retoucher:
                try:
                    user_profile = retoucher.profile
                    if user_profile and user_profile.telegram_id:
                        telegram_id_to_send = user_profile.telegram_id
                        message_text=f"Правка по рендеру для продукта {render_instance.Product.Barcode}."
                        try:
                            async_task(
                                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                                chat_id=telegram_id_to_send,
                                text=message_text
                            )
                            print(f"Уведомление отправлено ретушеру {retoucher.username} (TG ID: {telegram_id_to_send})")
                        except Exception as e:
                            print(f"Не удалось отправить уведомление ретушеру {retoucher.username} (TG ID: {telegram_id_to_send}): {e}")
                    else:
                        print(f"У ретушера {retoucher.username} найден профиль, но отсутствует telegram_id.")
                except UserProfile.DoesNotExist:
                    print(f"Для ретушера {retoucher.username} не найден связанный UserProfile.")
                except AttributeError:
                     print(f"Не удалось получить доступ к атрибуту 'profile' для ретушера {retoucher.username}.")
            else:
                print(f"Ретушер не назначен для Render ID {render_instance.id}, уведомление не отправлено.")
            # --- КОНЕЦ БЛОКА ОТПРАВКИ УВЕДОМЛЕНИЯ ---

            return Response({"status": "Отправлено на правки ретушеру."}, status=status.HTTP_200_OK)

        except (RetouchStatus.DoesNotExist, SeniorRetouchStatus.DoesNotExist):
             return Response({"detail": "Необходимые статусы (RetouchStatus=4 или SeniorRetouchStatus=2) не найдены в базе данных."}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e: # Перехватываем ValidationError отдельно
            return Response({"detail": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": f"Произошла ошибка: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#работа с отклоненными - вернуть в очередь рендера
class ReturnModerationUploadToRenderQueue(APIView):
    """
    Эндпоинт для возврата продукта в очередь рендера.
    Обновляет ReturnToRenderComplete = True.
    Метод: POST
    URL: /rd/moderation-uploads/{pk}/return-to-render-queue/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        moderation_upload = get_object_or_404(ModerationUpload, pk=pk)
        render_instance = moderation_upload.RenderPhotos
        if not render_instance:
            return Response({"detail": "Связанный объект Render не найден."}, status=status.HTTP_404_NOT_FOUND)

        product_instance = render_instance.Product
        if not product_instance:
            return Response({"detail": "Связанный объект Product не найден."}, status=status.HTTP_404_NOT_FOUND)

        try:
            with transaction.atomic():
                # Обновляем Product
                product_instance.IsOnRender = False
                product_instance.RejectComment = moderation_upload.RejectComment
                product_instance.save()

                # Обновляем ModerationUpload
                moderation_upload.ReturnToRenderComplete = True
                moderation_upload.save()

            return Response({"status": "Продукт возвращен в очередь рендера."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": f"Произошла ошибка: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#работа с отклоненными - исправлено, вернуть в загрузку
class MarkModerationUploadFixed(APIView):
    """
    Эндпоинт для пометки как 'Исправлено' и возврата в очередь загрузки.
    Обновляет ReturnToRenderComplete = True.
    Метод: POST
    URL: /rd/moderation-uploads/{pk}/mark-fixed-return-to-upload/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        moderation_upload = get_object_or_404(ModerationUpload, pk=pk)
        render_instance = moderation_upload.RenderPhotos
        if not render_instance:
            return Response({"detail": "Связанный объект Render не найден."}, status=status.HTTP_404_NOT_FOUND)

        try:
            with transaction.atomic():
                # Обновляем Render
                render_instance.IsOnUpload = False
                render_instance.save()

                # Обновляем ModerationUpload
                moderation_upload.ReturnToRenderComplete = True
                moderation_upload.save()

            return Response({"status": "Отмечено как исправлено, возвращено в очередь загрузки."}, status=status.HTTP_200_OK)
        except Exception as e:
             return Response({"detail": f"Произошла ошибка: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#работа с отклоненными - на съемку
class SendModerationUploadForReshoot(APIView):
    """
    Эндпоинт для отправки продукта на пересъемку.
    Обновляет ReturnToRenderComplete = True.
    Метод: POST
    URL: /rd/moderation-uploads/{pk}/send-for-reshoot/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        moderation_upload = get_object_or_404(ModerationUpload, pk=pk)
        render_instance = moderation_upload.RenderPhotos
        if not render_instance:
            return Response({"detail": "Связанный объект Render не найден."}, status=status.HTTP_404_NOT_FOUND)

        try:
            retouch_status_7 = get_object_or_404(RetouchStatus, pk=7)
            check_result_50 = get_object_or_404(RenderCheckResult, pk=50)

            with transaction.atomic():
                # Обновляем Render
                render_instance.RetouchStatus = retouch_status_7
                render_instance.IsSuitable = False
                render_instance.CheckResult.clear()
                render_instance.CheckResult.add(check_result_50)
                render_instance.save()

                # Обновляем ModerationUpload
                moderation_upload.ReturnToRenderComplete = True
                moderation_upload.save()

            return Response({"status": "Отправлено на пересъемку."}, status=status.HTTP_200_OK)

        except (RetouchStatus.DoesNotExist, RenderCheckResult.DoesNotExist):
             return Response({"detail": "Необходимые статусы (RetouchStatus=7 или RenderCheckResult=50) не найдены в базе данных."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
             return Response({"detail": f"Произошла ошибка: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#забрать отклоненные рендеры на съемку
def get_rejected_photos_for_shooting(request, count):
    """
    API endpoint to get a list of product barcodes whose photos
    are rejected or in moderation and require shooting, with optional quotas.

    Args:
        request: HttpRequest object. May contain query parameters:
                 - limit_type_2 (float): Quota for STRequestType 2 (e.g., 0.2 for 20%).
                 - limit_type_3 (float): Quota for STRequestType 3 (e.g., 0.05 for 5%).
        count (int): The total maximum number of barcodes to return.

    Returns:
        JsonResponse: A list of barcodes or an error message.
    """
    try:
        # Convert count to an integer and check if it's positive
        limit = int(count)
        if limit <= 0:
            return HttpResponseBadRequest("Count must be a positive integer.")
    except ValueError:
        return HttpResponseBadRequest("Invalid count value.")

    try:
        # Get optional quotas from query parameters, default to 0.0
        limit_type_2_quota = float(request.GET.get('limit_type_2', 0.0))
        limit_type_3_quota = float(request.GET.get('limit_type_3', 0.0))
    except ValueError:
        return HttpResponseBadRequest("Invalid quota format. Please provide a float.")

    # List of IDs for RenderCheckResult that indicate a reshoot is needed
    rejected_check_result_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 50]
    
    # Get IDs/barcodes for blocked items
    blocked_shop_ids = Blocked_Shops.objects.values_list('shop_id', flat=True)
    blocked_category_ids = ProductCategory.objects.filter(IsBlocked=True).values_list('id', flat=True)
    blocked_barcodes = Blocked_Barcode.objects.values_list('barcode', flat=True)
    nofoto_barcodes = Nofoto.objects.values_list('product__barcode', flat=True)

    # Photo moderation statuses of interest
    photo_moderation_statuses = ["Отклонено"]

    # --- Link render.Product.CategoryID to core.ProductCategory.STRequestType ---
    # Get CategoryIDs for each STRequestType
    type_1_category_ids = ProductCategory.objects.filter(STRequestType_id=1).values_list('id', flat=True)
    type_2_category_ids = ProductCategory.objects.filter(STRequestType_id=2).values_list('id', flat=True)
    type_3_category_ids = ProductCategory.objects.filter(STRequestType_id=3).values_list('id', flat=True)

    # --- Base query with all common filters and new sorting ---
    base_query = Product.objects.filter(
        IsOnOrder=False,
        PhotoModerationStatus__in=photo_moderation_statuses,
        render__CheckResult__id__in=rejected_check_result_ids,
        WMSQuantity__gt=0
    ).exclude(
        ShopID__in=blocked_shop_ids
    ).exclude(
        CategoryID__in=blocked_category_ids
    ).exclude(
        Barcode__in=blocked_barcodes
    ).exclude(
        Barcode__in=nofoto_barcodes
    ).distinct().order_by('-WMSQuantity', 'render__CheckTimeStart') # <-- Updated sorting

    # --- Apply quotas to fetch barcodes ---
    final_barcodes = []
    
    # Calculate limits for each type
    limit_type_2 = math.floor(limit * limit_type_2_quota)
    limit_type_3 = math.floor(limit * limit_type_3_quota)

    # Fetch Type 2 barcodes if a limit is set
    if limit_type_2 > 0:
        barcodes_type_2 = list(base_query.filter(
            CategoryID__in=type_2_category_ids
        ).values_list('Barcode', flat=True)[:limit_type_2])
        final_barcodes.extend(barcodes_type_2)

    # Fetch Type 3 barcodes if a limit is set
    if limit_type_3 > 0:
        barcodes_type_3 = list(base_query.filter(
            CategoryID__in=type_3_category_ids
        ).exclude(
            Barcode__in=final_barcodes
        ).values_list('Barcode', flat=True)[:limit_type_3])
        final_barcodes.extend(barcodes_type_3)

    # Fetch Type 1 barcodes to fill the remaining slots
    remaining_limit = limit - len(final_barcodes)
    if remaining_limit > 0:
        barcodes_type_1 = list(base_query.filter(
            CategoryID__in=type_1_category_ids
        ).exclude(
            Barcode__in=final_barcodes
        ).values_list('Barcode', flat=True)[:remaining_limit])
        final_barcodes.extend(barcodes_type_1)

    return JsonResponse(final_barcodes, safe=False)

#поставить массовый блок рендера
class BlockProductsForRetouch(APIView):
    """
    Эндпоинт для массовой блокировки продуктов для ретуши.
    Принимает массив штрихкодов и устанавливает IsRetouchBlock=True
    для всех найденных продуктов.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        barcodes = request.data.get('barcodes')

        if not barcodes:
            return Response(
                {"error": "Необходимо передать массив 'barcodes'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(barcodes, list):
            return Response(
                {"error": "'barcodes' должен быть массивом."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not all(isinstance(barcode, str) for barcode in barcodes):
            return Response(
                {"error": "Все элементы в 'barcodes' должны быть строками."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Находим продукты по списку штрихкодов
        products_to_update = Product.objects.filter(Barcode__in=barcodes)

        if not products_to_update.exists():
            return Response(
                {"message": "Продукты с указанными штрихкодами не найдены."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Обновляем поле IsRetouchBlock
        updated_count = products_to_update.update(IsRetouchBlock=True)

        return Response(
            {"message": f"Успешно обновлено {updated_count} продуктов. IsRetouchBlock установлено в True."},
            status=status.HTTP_200_OK
        )

class UploadedModerationDataView(generics.ListAPIView):
    serializer_class = ModerationStudioUploadSerializer
    pagination_class = None  # Отключаем пагинацию

    def get_queryset(self):
        """
        Этот метод возвращает queryset, который будет использован для ответа.
        """
        # select_related используется для оптимизации запросов к БД,
        # чтобы избежать N+1 проблемы при доступе к связанным объектам.
        queryset = ModerationStudioUpload.objects.select_related(
            'RenderPhotos__st_request_product__product', # для доступа к barcode
            'RenderPhotos'                             # для доступа к retouch_link
        ).filter(IsUploaded=True).order_by('-UploadTimeStart')
        return queryset

class RecentUploadedModerationDataView(generics.ListAPIView):
    serializer_class = ModerationStudioUploadSerializer
    pagination_class = None  # Отключаем пагинацию
    renderer_classes = [JSONRenderer]

    def get_queryset(self):
        """
        Этот метод возвращает queryset, который будет использован для ответа.
        Он выбирает только записи, у которых UploadTimeStart входит в указанное
        количество последних дней, переданное через URL.
        """
        days_param = self.kwargs.get('days_ago') # Получаем параметр 'days_ago' из URL

        if days_param is None:
            # Можно установить значение по умолчанию или выбросить ошибку, если параметр обязателен
            # В данном случае, URL-конфигурация требует его, так что этот блок может быть избыточным
            # если URL всегда будет содержать days_ago
            cutoff_date = timezone.now() - timedelta(days=7) # По умолчанию 7 дней, если вдруг параметр не пришел
        else:
            try:
                days = int(days_param)
                if days < 0:
                    # Отрицательное количество дней не имеет смысла в данном контексте
                    raise ValidationError("Количество дней не может быть отрицательным.")
                # Проверка на слишком большое значение, чтобы избежать переполнения timedelta
                # datetime.MINYEAR (год 1) является практическим пределом для timedelta в днях назад
                # (timezone.now().year - MINYEAR) * 366 примерно максимальное кол-во дней
                max_days = (timezone.now().year - MINYEAR) * 366
                if days > max_days:
                    raise ValidationError(f"Слишком большой период. Максимальное количество дней: {max_days}.")
                cutoff_date = timezone.now() - timedelta(days=days)
            except ValueError:
                # Если параметр не может быть преобразован в целое число
                raise ValidationError("Некорректное значение для количества дней. Ожидается целое число.")


        # select_related используется для оптимизации запросов к БД,
        # чтобы избежать N+1 проблемы при доступе к связанным объектам.
        queryset = ModerationStudioUpload.objects.select_related(
            'RenderPhotos__st_request_product__product',  # для доступа к barcode
            'RenderPhotos'                                # для доступа к retouch_link
        ).filter(
            IsUploaded=True,
            UploadTimeStart__gte=cutoff_date  # Фильтр по дате начала загрузки
        ).order_by('-UploadTimeStart')
        return queryset

## ВСЕ РЕНДЕРЫ
class AllRenderListView(generics.ListAPIView):
    """
    Предоставляет полный список всех объектов Render с вложенными данными,
    используя SeniorRenderSerializer.

    Поддерживает:
    - Пагинацию (через StandardResultsSetPagination)
    - Сортировку (ordering) по полям: pk, created_at, updated_at, RetouchTimeEnd
    - Фильтрацию (filtering) по полям: IsSuitable, RetouchStatus__id, Retoucher__id и по списку Product__Barcode
    """
    serializer_class = SeniorRenderSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    
    # Заменяем filterset_fields на filterset_class для использования кастомной логики
    # filterset_fields = ['IsSuitable', 'RetouchStatus__id', 'Retoucher__id'] # <-- ЭТА СТРОКА УДАЛЕНА
    filterset_class = RenderFilter # <-- ЭТА СТРОКА ДОБАВЛЕНА
    
    ordering_fields = ['id', 'created_at', 'updated_at', 'RetouchTimeEnd', 'CheckTimeStart']
    ordering = ['-id']

    def get_queryset(self):
        """
        Переопределяем метод для получения queryset.
        Это лучший способ для добавления оптимизации запросов к базе данных.
        """
        queryset = Render.objects.all().select_related(
            'Product',
            'Retoucher',
            'RetouchStatus'
        ).prefetch_related(
            'CheckResult'
        )
        return queryset


### Среднее время от начала проверки рендера
def format_timedelta(delta):
    """Преобразует объект timedelta в строку формата 'дд чч:мм:сс'."""
    if not isinstance(delta, timedelta):
        return None
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days:02d} {hours:02d}:{minutes:02d}:{seconds:02d}"


def get_render_check_stats(request):
    """
    Эндпоинт для вычисления средней длительности проверки рендеров,
    а также для получения списка из 20 рендеров с максимальной длительностью.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

    try:
        # --- 1. Определение всех фильтров (без изменений) ---
        rejected_check_result_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 50]
        photo_moderation_statuses = ["Отклонено"]

        blocked_shop_ids = Blocked_Shops.objects.values_list('shop_id', flat=True)
        blocked_category_ids = ProductCategory.objects.filter(IsBlocked=True).values_list('id', flat=True)
        blocked_barcodes = Blocked_Barcode.objects.values_list('barcode', flat=True)
        nofoto_barcodes = Nofoto.objects.values_list('product__barcode', flat=True)

        # --- 2. Построение базового запроса (без изменений) ---
        renders_query = Render.objects.filter(
            CheckResult__id__in=rejected_check_result_ids,
            Product__IsOnOrder=False,
            Product__PhotoModerationStatus__in=photo_moderation_statuses,
            Product__WMSQuantity__gt=0,
            CheckTimeStart__isnull=False
        ).exclude(
            Q(Product__ShopID__in=blocked_shop_ids) |
            Q(Product__CategoryID__in=blocked_category_ids) |
            Q(Product__Barcode__in=blocked_barcodes) |
            Q(Product__Barcode__in=nofoto_barcodes)
        ).distinct()

        # --- 3. Выполнение запросов ---
        
        # Запрос 1: Получаем среднее значение
        aggregates = renders_query.aggregate(
            average_duration=Avg(Now() - F('CheckTimeStart'))
        )
        
        # НОВОЕ: Запрос 2: Находим 20 записей с самой большой длительностью.
        # Используем select_related для оптимизации доступа к Product.Barcode.
        top_20_renders = renders_query.select_related('Product').order_by('CheckTimeStart')[:20]
        
        # --- 4. Форматирование результата ---
        avg_timedelta = aggregates.get('average_duration')
        formatted_avg = format_timedelta(avg_timedelta)
        
        # НОВОЕ: Формируем список из топ-20
        top_renders_data = []
        now = timezone.now() # Получаем текущее время один раз для консистентности
        
        for render_item in top_20_renders:
            duration = now - render_item.CheckTimeStart
            top_renders_data.append({
                "barcode": render_item.Product.Barcode,
                "duration": format_timedelta(duration)
            })

        if formatted_avg: # Если данные найдены
            response_data = {
                "average_duration": formatted_avg,
                "top_longest_renders": top_renders_data
            }
            status_code = 200
        else:
            response_data = {
                "message": "Нет данных для расчета",
                "average_duration": None,
                "top_longest_renders": []
            }
            status_code = 404

        return JsonResponse(response_data, status=status_code)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
