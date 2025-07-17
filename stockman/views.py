from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.timezone import localtime
from django.http import HttpResponse
from collections import defaultdict, Counter
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter
from rest_framework.generics import ListAPIView
from django_q.tasks import async_task
from django.db.models import Count, Q, ExpressionWrapper, F, DurationField, Subquery, OuterRef, Exists
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
from tgbot.tgbot import send_order_accept_message
from openpyxl import Workbook

from core.models import (
    Order,
    OrderProduct,
    OrderStatus,
    Product,
    ProductMoveStatus,
    STRequest,
    STRequestProduct,
    STRequestType,
    STRequestStatus,
    STRequestHistory,
    STRequestHistoryOperations,
    STRequestPhotoTime,
    ProductOperationTypes,
    ProductOperation,
    Invoice,
    InvoiceProduct,
    )
from .serializers import (
    OrderSerializer,
    OrderStatusSerializer,
    OrderDetailSerializer,
    STRequestSerializer,
    STRequestDetailSerializer,
    STRequestStatusSerializer,
    InvoiceSerializer,
    InvoiceDetailSerializer,
    ProductMoveStatusSerializer,
    CurrentProductSerializer,
    OrderProductSerializer,
    ProblematicProduct1Serializer,
    ProblematicProduct2Serializer,
    ProblematicProduct3Serializer
    )
from .pagination import StandardResultsSetPagination
from .filters import STRequestFilter, InvoiceFilter, CurrentProductFilter


#список заказов
class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = Order.objects.all()
        # Аннотации для вычисляемых полей (количества и разница дат)
        qs = qs.annotate(
            total_products=Count('orderproduct'),
            priority_products=Count('orderproduct', filter=Q(orderproduct__product__priority=True)),
            accepted_products=Count('orderproduct', filter=Q(orderproduct__accepted=True)),
            acceptance_time=ExpressionWrapper(F('accept_date_end') - F('accept_date'), output_field=DurationField())
        )

        params = self.request.query_params
        date_format = "%d.%m.%Y %H:%M:%S"

        # Фильтр по номерам заказов (передаётся массивом через запятую)
        order_numbers = params.get('order_numbers')
        if order_numbers:
            order_numbers_list = [num.strip() for num in order_numbers.split(',') if num.strip().isdigit()]
            if order_numbers_list:
                qs = qs.filter(OrderNumber__in=order_numbers_list)

        # Фильтр по статусам (массив id через запятую)
        statuses = params.get('statuses')
        if statuses:
            status_list = [s.strip() for s in statuses.split(',') if s.strip().isdigit()]
            if status_list:
                qs = qs.filter(status__id__in=status_list)

        # Фильтрация по дате создания (включительно)
        date_from = params.get('date_from')
        date_to = params.get('date_to')
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, date_format)
                qs = qs.filter(date__gte=dt_from)
            except ValueError:
                pass
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, date_format)
                qs = qs.filter(date__lte=dt_to)
            except ValueError:
                pass

        # Фильтрация по дате сборки
        assembly_date_from = params.get('assembly_date_from')
        assembly_date_to = params.get('assembly_date_to')
        if assembly_date_from:
            try:
                ad_from = datetime.strptime(assembly_date_from, date_format)
                qs = qs.filter(assembly_date__gte=ad_from)
            except ValueError:
                pass
        if assembly_date_to:
            try:
                ad_to = datetime.strptime(assembly_date_to, date_format)
                qs = qs.filter(assembly_date__lte=ad_to)
            except ValueError:
                pass

        # Фильтрация по дате приемки (начало)
        accept_date_from = params.get('accept_date_from')
        accept_date_to = params.get('accept_date_to')
        if accept_date_from:
            try:
                ac_from = datetime.strptime(accept_date_from, date_format)
                qs = qs.filter(accept_date__gte=ac_from)
            except ValueError:
                pass
        if accept_date_to:
            try:
                ac_to = datetime.strptime(accept_date_to, date_format)
                qs = qs.filter(accept_date__lte=ac_to)
            except ValueError:
                pass

        # Фильтрация по штрихкодам (через OrderProduct -> Product)
        barcodes = params.get('barcodes')
        if barcodes:
            barcode_list = [b.strip() for b in barcodes.split(',') if b.strip()]
            qs = qs.filter(orderproduct__product__barcode__in=barcode_list).distinct()
            self.barcode_list = barcode_list  # сохраняем для вычисления "не найденных"
        else:
            self.barcode_list = None

        # Сортировка – можно передать через параметр ordering, например:
        # ?ordering=OrderNumber или ?ordering=-date
        ordering = params.get('ordering')
        if ordering:
            ordering_fields = [field.strip() for field in ordering.split(',')]
            qs = qs.order_by(*ordering_fields)

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Если фильтруется по штрихкодам – вычисляем, какие из переданных не найдены
        not_found_barcodes = []
        if self.barcode_list:
            found_barcodes = set(OrderProduct.objects.filter(order__in=queryset)
                                 .values_list('product__barcode', flat=True))
            not_found_barcodes = list(set(self.barcode_list) - found_barcodes)

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        data = self.get_paginated_response(serializer.data).data
        if self.barcode_list:
            data['not_found_barcodes'] = not_found_barcodes
        return Response(data)

#эндпоинт на список статусов заказов для фильтра на фронте
class OrderStatusListView(generics.ListAPIView):
    queryset = OrderStatus.objects.all()
    serializer_class = OrderStatusSerializer
    pagination_class = None

#Детали заказа
class OrderDetailAPIView(APIView):
    def get(self, request, order_number, format=None):
        order = get_object_or_404(Order, OrderNumber=order_number)
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data)

#Приемка заказа товароведом
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_accept_start(request, ordernumber):
    # Поиск заказа по OrderNumber
    try:
        order = Order.objects.get(OrderNumber=ordernumber)
    except Order.DoesNotExist:
        return Response({"error": "Заказ не найден."}, status=status.HTTP_404_NOT_FOUND)
    
    # Установка пользователя, который принял заказ
    order.accept_user = request.user
    # Установка даты и времени приемки
    order.accept_date = timezone.now()
    
    # Обновление статуса заказа на статус с id=4
    try:
        new_status = OrderStatus.objects.get(pk=4)
    except OrderStatus.DoesNotExist:
        return Response({"error": "Статус заказа с id 4 не найден."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    order.status = new_status
    order.save()
    
    return Response({"message": "Приемка заказа начата успешно."}, status=status.HTTP_200_OK)

#Проверка товара в заказе
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_check_product(request, ordernumber, barcode):
    # Поиск заказа по OrderNumber
    order = get_object_or_404(Order, OrderNumber=ordernumber)
    
    # Поиск товара в заказе через модель OrderProduct
    try:
        order_product = OrderProduct.objects.get(order=order, product__barcode=barcode)
    except OrderProduct.DoesNotExist:
        return Response(
            {"error": "Штрихкод не найден в этом заказе."},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Если товар уже принят (accepted=True), возвращаем ошибку
    if order_product.accepted:
        return Response(
            {"error": "Данный товар уже принят в этом заказе."},
            status=status.HTTP_400_BAD_REQUEST
        )

    product = order_product.product
    # Формируем информацию о товаре
    product_data = {
        "barcode": product.barcode,
        "name": product.name,
        "move_status": product.move_status.name if product.move_status else None,
        "info": product.info
    }
    
    # Проверка наличия товара в заявках со статусами 2 и 3
    st_req_product = STRequestProduct.objects.filter(
        product=product,
        request__status__id__in=[2, 3]
    ).first()
    
    if st_req_product:
        duplicate = True
        strequestnumber = st_req_product.request.RequestNumber
    else:
        duplicate = False
        strequestnumber = ""
    
    response_data = {
        "product": product_data,
        "duplicate": duplicate,
        "strequestnumber": strequestnumber
    }
    
    return Response(response_data, status=status.HTTP_200_OK)

#Приемка товара в заказе
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_accept_product(request, ordernumber):
    # Поиск заказа по OrderNumber
    try:
        order = Order.objects.get(OrderNumber=ordernumber)
    except Order.DoesNotExist:
        return Response({"error": "Заказ не найден."}, status=status.HTTP_404_NOT_FOUND)
    
    # Получаем массив штрихкодов из тела запроса
    barcodes = request.data.get("barcodes")
    if barcodes is None:
        return Response({"error": "Массив штрихкодов не передан."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(barcodes, list):
        return Response({"error": "Баркоды должны передаваться в виде списка."}, status=status.HTTP_400_BAD_REQUEST)

    results = []
    products_with_info_details = [] # Список для хранения кортежей (barcode, info)

    for barcode in barcodes:
        barcode_result = {"barcode": barcode}
        # Находим продукт по штрихкоду
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            barcode_result["error"] = "Продукт с данным штрихкодом не найден."
            results.append(barcode_result)
            continue

        # <<< НАЧАЛО ДОПОЛНЕНИЯ >>>
        # Проверяем поле info продукта
        if product.info and product.info.strip(): # strip() для удаления пробельных символов по краям
            products_with_info_details.append((product.barcode, product.info))
        # <<< КОНЕЦ ДОПОЛНЕНИЯ >>>

        # Обновляем поля модели Product
        product.move_status_id = 3  # статус "приемки", предполагается, что статус с id=3 существует
        product.income_stockman = request.user
        product.income_date = timezone.now()
        product.save()

        # Создаем запись в ProductOperation
        try:
            operation_type = ProductOperationTypes.objects.get(pk=3)
        except ProductOperationTypes.DoesNotExist:
            barcode_result["error"] = "Тип операции с id 3 не найден."
            # Важно: если продукт уже обработан и info добавлено, но тут ошибка,
            # сообщение все равно будет отправлено в конце. Это поведение можно изменить при необходимости.
            results.append(barcode_result)
            continue 

        ProductOperation.objects.create(
            product=product,
            operation_type=operation_type,
            user=request.user,
            # date выставится автоматически через auto_now_add (если так настроена модель ProductOperation)
        )

        # Обновляем запись в OrderProduct
        try:
            order_product = OrderProduct.objects.get(order=order, product=product)
        except OrderProduct.DoesNotExist:
            barcode_result["error"] = "Продукт не найден в заказе."
            results.append(barcode_result)
            continue

        order_product.accepted = True
        order_product.accepted_date = timezone.now()
        order_product.save()

        barcode_result["status"] = "Продукт успешно принят."
        results.append(barcode_result)

    # <<< НАЧАЛО ДОПОЛНЕНИЯ - ОТПРАВКА СООБЩЕНИЯ >>>
    if products_with_info_details:
        message_lines = ["Приняты товары с инфо:"]
        for bc, info_text in products_with_info_details:
            message_lines.append(f"{bc} - {info_text}")
        
        telegram_message_text = "\n".join(message_lines)
        chat_id_to_send = '-1002559221974'
        thread_id_to_send = 2
        
        async_task(
            'telegram_bot.tasks.send_message_task',
            chat_id=chat_id_to_send,
            text=telegram_message_text,
            message_thread_id=thread_id_to_send
        )
    # <<< КОНЕЦ ДОПОЛНЕНИЯ - ОТПРАВКА СООБЩЕНИЯ >>>

    return Response({"results": results}, status=status.HTTP_200_OK)

#получение следующего номера заявки
def get_next_request_number():
    """
    Вспомогательная функция для вычисления следующего номера заявки.
    Если заявок нет или RequestNumber некорректен, начальное значение равно 1.
    """
    last_request = STRequest.objects.order_by('-RequestNumber').first()
    if last_request:
        try:
            last_number = int(last_request.RequestNumber)
        except ValueError:
            last_number = 0
    else:
        last_number = 0
    new_number = last_number + 1
    return str(new_number)

#создание новой заявки (пустой черновик)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def strequest_create(request):
    next_number = get_next_request_number()
    
    try:
        status_instance = STRequestStatus.objects.get(pk=2)
    except STRequestStatus.DoesNotExist:
        return Response(
            {"error": "Статус заявки с id=1 не найден."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    new_request = STRequest.objects.create(
        RequestNumber=next_number,
        stockman=request.user,
        status=status_instance
        # creation_date можно не передавать, если в модели стоит auto_now_add=True
    )
    
    return Response({"RequestNumber": new_request.RequestNumber}, status=status.HTTP_201_CREATED)

#создание заявки с шк
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def strequest_create_barcodes(request):
    barcodes = request.data.get("barcodes")
    if barcodes is None:
        return Response({"error": "Массив штрихкодов не передан."}, status=status.HTTP_400_BAD_REQUEST)
    if not isinstance(barcodes, list):
        return Response({"error": "Баркоды должны передаваться в виде списка."}, status=status.HTTP_400_BAD_REQUEST)
    
    # Получаем следующий номер заявки (предполагается, что функция get_next_request_number существует)
    next_number = get_next_request_number() 
    
    # Получаем статус заявки с id=2
    try:
        status_instance = STRequestStatus.objects.get(pk=2)
    except STRequestStatus.DoesNotExist:
        return Response({"error": "Статус заявки с id=2 не найден."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Создаем новую заявку
    new_request = STRequest.objects.create(
        RequestNumber=next_number,
        stockman=request.user, # Кладовщик, создающий заявку
        status=status_instance
    )
    
    # Получаем тип операции для ProductOperation с id=71
    try:
        product_operation_type = ProductOperationTypes.objects.get(id=71)
    except ProductOperationTypes.DoesNotExist:
        return Response({"error": "Тип операции ProductOperation с id=71 не найден."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    barcode_results = []
    # Привязываем каждый штрихкод к созданной заявке и создаем запись ProductOperation
    for barcode_str in barcodes: # Изменил barcode на barcode_str для ясности, т.к. product тоже называется barcode
        if not isinstance(barcode_str, str): # Дополнительная проверка типа элемента списка
            barcode_results.append({"barcode": barcode_str, "error": "Штрихкод должен быть строкой."})
            continue

        result_item = {"barcode": barcode_str}
        try:
            product_instance = Product.objects.get(barcode=barcode_str)
        except Product.DoesNotExist:
            result_item["error"] = "Продукт с данным штрихкодом не найден."
            barcode_results.append(result_item)
            continue
        
        # Создаем связь в модели STRequestProduct
        STRequestProduct.objects.create(
            request=new_request,
            product=product_instance
        )
        
        # Создаем запись ProductOperation
        ProductOperation.objects.create(
            product=product_instance,
            operation_type=product_operation_type,
            user=request.user, # Пользователь, который выполнил операцию (создал заявку)
            comment=f"номер заявки {new_request.RequestNumber}" # Комментарий к операции
            # date будет установлено автоматически благодаря auto_now_add=True в модели
        )
        
        result_item["status"] = "Продукт успешно привязан к заявке и создана запись операции."
        barcode_results.append(result_item)

    if not new_request.STRequestTypeBlocked:
        new_type = determine_and_set_strequest_type(new_request.RequestNumber)
        # По желанию, добавим информацию о назначенном типе в ответ
        if new_type:
            assigned = {
                "STRequestTypeAssigned": new_type.id,
                "STRequestTypeName": new_type.name
            }
        else:
            assigned = {"warning": "Не удалось определить тип заявки автоматически."}
    else:
        assigned = {"info": "Автоматическая смена типа заявки заблокирована."}
    
    response_data = {
        "RequestNumber": new_request.RequestNumber,
        "barcode_results": barcode_results
    }
    
    return Response(response_data, status=status.HTTP_201_CREATED)

#Список заявок для товароведов
class STRequestSearchListView(generics.ListAPIView):
    """
    Эндпоинт для поиска заявок STRequest с фильтрацией, сортировкой и пагинацией.
    """
    serializer_class = STRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = STRequestFilter
    ordering_fields = [
        'RequestNumber',
        'creation_date',
        'stockman__first_name',
        'photo_date',
        'photographer__first_name',
        'products_count',
        'priority_products_count',
        'status',
    ]
    ordering = ['-creation_date']
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = STRequest.objects.all().annotate(
            products_count=Count('strequestproduct'),
            priority_products_count=Count('strequestproduct', filter=Q(strequestproduct__product__priority=True))
        )
        return qs

#Детальная информация заявки
class STRequestDetailView(generics.RetrieveAPIView):
    """
    Эндпоинт для получения детальной информации по заявке.
    URL: strequest-detail/<STRequestNumber>/
    """
    queryset = STRequest.objects.all()
    serializer_class = STRequestDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'RequestNumber'
    lookup_url_kwarg = 'STRequestNumber'
    ordering = ['-id']

#Список статусов заявок для фильтра на фронте
class STRequestStatusListView(generics.ListAPIView):
    queryset = STRequestStatus.objects.all().order_by('id')
    serializer_class = STRequestStatusSerializer
    pagination_class = None

#Добавление штрихкодов в заявки
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def strequest_add_product(request, STRequestNumber, Barcode):
    # 1. Проверка существования продукта по штрихкоду
    try:
        product = Product.objects.get(barcode=Barcode)
    except Product.DoesNotExist:
        return Response({"error": "такого товара нет в базе"}, status=status.HTTP_404_NOT_FOUND)
    
    # 2. Проверка статуса движения продукта (ожидается статус 3)
    if not product.move_status or product.move_status.id != 3:
        return Response({"error": "Товар не в статусе Принят"}, status=status.HTTP_400_BAD_REQUEST)
    
    # 3. Проверка наличия продукта в заявках со статусом 2 или 3
    existing_products = STRequestProduct.objects.filter(
        product=product,
        request__status__id__in=[2, 3] # Предполагается, что у STRequest есть поле status, которое является ForeignKey на модель со статусами, имеющую поле id
    )
    if existing_products.exists():
        # Собираем номера заявок, где найден продукт
        strequest_numbers = list(existing_products.values_list("request__RequestNumber", flat=True).distinct())
        return Response(
            {"error": f"Товар находится в заявке {', '.join(strequest_numbers)}"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # 4. Получение заявки по STRequestNumber
    try:
        st_request = STRequest.objects.get(RequestNumber=STRequestNumber)
    except STRequest.DoesNotExist:
        return Response({"error": "Заявка не найдена."}, status=status.HTTP_404_NOT_FOUND)
    
    # 5. Создаем запись STRequestProduct для связи продукта и заявки
    STRequestProduct.objects.create(
        request=st_request,
        product=product
    )
    
    # 6. Создаем запись ProductOperation
    try:
        operation_type_instance = ProductOperationTypes.objects.get(id=71)
    except ProductOperationTypes.DoesNotExist:
        return Response(
            {"error": "Тип операции для ProductOperation с id=71 не найден."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    ProductOperation.objects.create(
        product=product,
        operation_type=operation_type_instance,
        user=request.user,
        # date будет установлено автоматически благодаря auto_now_add=True в модели
        comment=f"номер заявки {st_request.RequestNumber}" # Используем f-string для формирования комментария
    )

    # 7. Автоматически пересчитываем STRequestType, если не заблокировано
    result = {"message": "Продукт успешно добавлен в заявку."}
    if not st_request.STRequestTypeBlocked:
        new_type = determine_and_set_strequest_type(st_request.RequestNumber)
        if new_type:
            result.update({
                "STRequestTypeAssigned": new_type.id,
                "STRequestTypeName": new_type.name
            })
        else:
            result["warning"] = "Не удалось определить тип заявки автоматически."
    else:
        result["info"] = "Автоматическая смена типа заявки заблокирована."
    
    return Response({"message": "Продукт успешно добавлен в заявку"}, status=status.HTTP_201_CREATED)

#удаление штрихкода из заявки
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def strequest_delete_barcode(request, STRequestNumber, Barcode):
    # 1. Проверка существования продукта
    try:
        product = Product.objects.get(barcode=Barcode)
    except Product.DoesNotExist:
        return Response({"error": "Данного штрихкода не существует."},
                        status=status.HTTP_404_NOT_FOUND)
    
    # 2. Проверка существования заявки
    try:
        st_request = STRequest.objects.get(RequestNumber=STRequestNumber)
    except STRequest.DoesNotExist:
        return Response({"error": "Заявка не найдена."},
                        status=status.HTTP_404_NOT_FOUND)
    
    # 3. Проверка, что продукт присутствует в заявке
    try:
        st_request_product = STRequestProduct.objects.get(request=st_request, product=product)
    except STRequestProduct.DoesNotExist:
        return Response({"error": "Данного штрихкода нет в этой заявке."},
                        status=status.HTTP_404_NOT_FOUND)
    
    # 4. Удаляем запись из STRequestProduct
    st_request_product.delete()
    
    # 5. Создаем запись ProductOperation с типом операции id=72
    try:
        operation_type_instance = ProductOperationTypes.objects.get(id=72)
    except ProductOperationTypes.DoesNotExist:
        return Response(
            {"error": "Тип операции для ProductOperation с id=72 не найден."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    ProductOperation.objects.create(
        product=product,
        operation_type=operation_type_instance,
        user=request.user,
        # date будет установлено автоматически благодаря auto_now_add=True в модели
        comment=f"номер заявки {st_request.RequestNumber}" 
    )
    
    return Response({"message": "Продукт успешно удалён из заявки и создана запись операции."}, status=status.HTTP_200_OK)

#Завершить приемку
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_accept_end(request, OrderNumber):
    # Получаем заказ по номеру
    try:
        order = Order.objects.get(OrderNumber=OrderNumber)
    except Order.DoesNotExist:
        return Response({"error": "Заказ не найден."}, status=status.HTTP_404_NOT_FOUND)
    
    # Устанавливаем дату завершения приемки
    order.accept_date_end = timezone.now()
    order.save()
    
    # Вычисляем время приемки, если установлена дата начала приемки
    if order.accept_date:
        time_diff = order.accept_date_end - order.accept_date
        time_diff_str = str(time_diff).split('.')[0]  # Убираем микросекунды
    else:
        time_diff_str = "неизвестно"
    
    # Получаем связанные записи OrderProduct
    order_products = OrderProduct.objects.filter(order=order)
    total_products = order_products.count()
    accepted_count = order_products.filter(accepted=True).count()
    
    # Получаем ФИО сотрудника, принявшего заказ
    if order.accept_user:
        accept_user_name = f"{order.accept_user.first_name} {order.accept_user.last_name}".strip()
    else:
        accept_user_name = "Неизвестно"
    
    # Формируем сообщение и обновляем статус заказа
    if total_products == accepted_count:
        # Все товары приняты, статус = 5
        order.status_id = 5  # Предполагается, что статус с id=5 существует
        message_text = (
            f"Заказ №{order.OrderNumber} принят.\n"
            f"Принял - {accept_user_name}\n"
            f"Количество принятых - {accepted_count}\n"
            f"Время приемки - {time_diff_str}"
        )
    else:
        # Не все товары приняты, статус = 6
        order.status_id = 6  # Предполагается, что статус с id=6 существует
        # Получаем список штрихкодов непринятых товаров
        not_accepted = order_products.filter(accepted=False)
        not_accepted_barcodes = "\n".join([prod.product.barcode for prod in not_accepted])
        message_text = (
            f"Заказ №{order.OrderNumber} принят с расхождениями.\n"
            f"Принял - {accept_user_name}\n"
            f"Количество принятых - {accepted_count}\n"
            f"Время приемки - {time_diff_str}\n"
            f"Непринятые:\n{not_accepted_barcodes}"
        )
    order.save()
    
    # Отправляем сообщение через телеграм-бота
    send_order_accept_message(message_text)
    
    return Response({"message": "Приемка завершена.", "telegram_message": message_text}, status=status.HTTP_200_OK)

#Эндпоинт листа накладных
class InvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = InvoiceFilter
    # Для сортировки используем маппинг полей:
    ordering_fields = {
        'InvoiceNumber': 'InvoiceNumber',
        'date': 'date',
        'creator': 'creator__first_name',  # можно расширить сортировку, если нужно учитывать фамилию
        'product_count': 'product_count'
    }
    ordering = ['InvoiceNumber']  # сортировка по умолчанию

    def get_queryset(self):
        # Аннотируем количество товаров для каждой накладной
        queryset = Invoice.objects.all().annotate(product_count=Count('invoiceproduct'))
        return queryset

#Эндпоинт детали накладной
class InvoiceDetailView(generics.RetrieveAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceDetailSerializer
    lookup_field = 'InvoiceNumber'
    lookup_url_kwarg = 'invoceNumber'

#Провека штрихкода для накладной
class InvoiceCheckBarcodeView(APIView):
    def post(self, request, format=None):
        barcode = request.data.get('barcode')
        if not barcode:
            return Response({"error": "Штрихкод не предоставлен."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return Response({"error": "Такого штрихкода нет в системе"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Сериализуем статус товародвижения
        move_status_serializer = ProductMoveStatusSerializer(product.move_status)
        
        # Ищем записи STRequestProduct для данного товара, где у заявки статус с id 2 или 3
        st_request_products = STRequestProduct.objects.filter(product=product, request__status__id__in=[2, 3])
        alert_requests = []
        for srp in st_request_products:
            if srp.request:
                alert_requests.append({
                    "RequestNumber": srp.request.RequestNumber,
                    "status": STRequestStatusSerializer(srp.request.status).data if srp.request.status else None,
                })
        
        # Если заявок не найдено, передаём "Нет заявок" на фронт
        if not alert_requests:
            alert_requests = [{"message": "Нет заявок"}]
        
        data = {
            "barcode": product.barcode,
            "name": product.name,
            "move_status": move_status_serializer.data,
            "alert_st_requests": alert_requests,
        }
        
        return Response(data, status=status.HTTP_200_OK)

#Создание накладной, отправка товара
class InvoiceCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        # Получаем массив штрихкодов
        barcodes = request.data.get("barcodes", [])
        if not barcodes or not isinstance(barcodes, list):
            return Response({"error": "Массив штрихкодов обязателен."}, status=status.HTTP_400_BAD_REQUEST)

        # Вычисляем новый номер накладной (преобразуем существующие номера в число, находим максимальное и прибавляем 1)
        invoice_numbers = Invoice.objects.exclude(InvoiceNumber__isnull=True).values_list("InvoiceNumber", flat=True)
        max_number = 0
        for num in invoice_numbers:
            try:
                n = int(num)
                max_number = max(max_number, n)
            except ValueError:
                continue
        new_number = str(max_number + 1)

        # Создаем новую накладную с текущей датой и аутентифицированным пользователем
        invoice = Invoice.objects.create(
            InvoiceNumber=new_number,
            date=timezone.now(),
            creator=request.user
        )

        # Получаем статус товародвижения с id=4
        try:
            new_move_status = ProductMoveStatus.objects.get(id=4)
        except ProductMoveStatus.DoesNotExist:
            return Response({"error": "ProductMoveStatus с id=4 не найден."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Получаем тип операции с id=4 для создания записи ProductOperation
        try:
            op_type = ProductOperationTypes.objects.get(id=4)
        except ProductOperationTypes.DoesNotExist:
            return Response({"error": "ProductOperationType с id=4 не найден."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Обрабатываем каждый штрихкод из запроса
        for barcode in barcodes:
            try:
                product = Product.objects.get(barcode=barcode)
            except Product.DoesNotExist:
                return Response({"error": f"Продукт со штрихкодом {barcode} не найден."},
                                status=status.HTTP_400_BAD_REQUEST)
            # Создаем связь InvoiceProduct
            InvoiceProduct.objects.create(invoice=invoice, product=product)
            # Обновляем move_status и устанавливаем Outcome_stockman и Outcome_date
            product.move_status = new_move_status
            product.outcome_stockman = request.user
            product.outcome_date = timezone.now()
            product.save()
            # Создаем запись ProductOperation
            ProductOperation.objects.create(
                product=product,
                operation_type=op_type,
                user=request.user,
                comment=f"Накладная {invoice.InvoiceNumber}"
            )

        data = {
            "InvoiceNumber": invoice.InvoiceNumber,
            "date": invoice.date.strftime("%d.%m.%Y %H:%M:%S"),
            "creator": f"{invoice.creator.first_name} {invoice.creator.last_name}",
            "barcodes": barcodes
        }
        return Response(data, status=status.HTTP_201_CREATED)

def check_and_notify_defect(product):
    # Получаем все операции для данного продукта с типом операции 25
    defect_operations = ProductOperation.objects.filter(product=product, operation_type__id=25).order_by('date')
    
    # Если количество записей ровно 3, формируем и отправляем сообщение
    if defect_operations.count() == 3:
        # Формируем заголовок сообщения с штрихкодом и наименованием продукта
        message = f'⚠️Товар {product.barcode} - "{product.name}" помечен браком 3 раза:\n'
        
        # Проходим по каждой операции и добавляем строку с датой и комментарием
        for op in defect_operations:
            # Приводим дату к локальному времени (если требуется)
            op_date = localtime(op.date).strftime("%d.%m.%Y %H:%M:%S")
            message += f'{op_date} - {op.comment}\n'
        
        # Отправляем сообщение в указанный чат
        chat_id_to_send="-1002559221974"
        thread_id="447"
        async_task(
            'telegram_bot.tasks.send_message_task', # Путь к нашей функции
            chat_id=chat_id_to_send,
            text=message,
            message_thread_id=thread_id
        )

#Пометить брак
class ProductMarkDefectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, barcode, format=None):
        # Получаем комментарий из тела запроса, он обязателен для брака
        comment = request.data.get("comment")
        if not comment:
            return Response({"error": "Комментарий обязателен для пометки брака."},
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Проверяем наличие продукта по barcode
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return Response({"error": "Продукт со штрихкодом не найден."},
                            status=status.HTTP_404_NOT_FOUND)
        
        # Обновляем статус товародвижения на 25
        try:
            defect_status = ProductMoveStatus.objects.get(id=25)
        except ProductMoveStatus.DoesNotExist:
            return Response({"error": "Статус товародвижения с id=25 не найден."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        product.move_status = defect_status
        product.save()
        
        # Создаем операцию с типом 25
        try:
            op_type = ProductOperationTypes.objects.get(id=25)
        except ProductOperationTypes.DoesNotExist:
            return Response({"error": "Тип операции с id=25 не найден."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        ProductOperation.objects.create(
            product=product,
            operation_type=op_type,
            user=request.user,
            comment=comment  # комментарий из запроса
        )

        check_and_notify_defect(product)
        
        return Response({"status": "ok"}, status=status.HTTP_200_OK)

#Пометить вскрыто
class ProductMarkOpenedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, barcode, format=None):
        # Получаем комментарий, если он передан, иначе пустая строка
        comment = request.data.get("comment", "").strip()
        # Если комментарий пустой, ставим "вскрыто"
        if not comment:
            comment = "вскрыто"
        
        # Проверяем наличие продукта по barcode
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return Response({"error": "Продукт со штрихкодом не найден."},
                            status=status.HTTP_404_NOT_FOUND)
        
        # Обновляем статус товародвижения на 30
        try:
            opened_status = ProductMoveStatus.objects.get(id=30)
        except ProductMoveStatus.DoesNotExist:
            return Response({"error": "Статус товародвижения с id=30 не найден."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        product.move_status = opened_status
        product.save()
        
        # Создаем операцию с типом 30
        try:
            op_type = ProductOperationTypes.objects.get(id=30)
        except ProductOperationTypes.DoesNotExist:
            return Response({"error": "Тип операции с id=30 не найден."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        ProductOperation.objects.create(
            product=product,
            operation_type=op_type,
            user=request.user,
            comment=comment  # Если комментарий не передан, здесь будет "вскрыто"
        )
        
        return Response({"status": "ok"}, status=status.HTTP_200_OK)

#Временно, потом убрать - закончить приемку всех заказов
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def order_accept_all(request):
    orders = Order.objects.filter(status=4)
    results = []

    # Передаём исходный Django HttpRequest вместо DRF request
    django_request = request._request

    for order in orders:
        # Вызываем уже определённую в этом же файле функцию order_accept_end
        response = order_accept_end(django_request, order.OrderNumber)
        results.append({
            "OrderNumber": order.OrderNumber,
            "message": response.data.get("message"),
            "telegram_message": response.data.get("telegram_message")
        })

    return Response({
        "message": "Приемка завершена для всех заказов со статусом 4.",
        "orders": results
    }, status=status.HTTP_200_OK)

#Список текущих продуктов на ФС
class PublicCurrentProducts(ListAPIView):
    """
    Эндпоинт для получения списка товаров с move_status = 3 (PublicCurrentProducts).
    Поддерживаются фильтры, сортировка и пагинация.
    """
    serializer_class = CurrentProductSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = CurrentProductFilter
    ordering_fields = [
        'barcode', 
        'name', 
        'seller', 
        'income_date', 
        'income_stockman__first_name',
        'info', 
        'priority',
        'currentstrequest_count',  # Сортировка по количеству текущих заявок
    ]
    ordering = ['income_date']

    def get_queryset(self):
        qs = Product.objects.filter(move_status__id=3).annotate(
            currentstrequest_count=Count(
                'strequestproduct', filter=Q(strequestproduct__request__status__id__in=[2, 3, 5])
            )
        )
        return qs

# вью для получения полного списка OrderProduct
class OrderProductListAPIView(APIView):
    def get(self, request, *args, **kwargs):
        # Сортировка: сначала по номеру заказа (от большего к меньшему), затем по штрихкоду
        order_products = OrderProduct.objects.all().order_by('-order__OrderNumber', 'product__barcode')
        serializer = OrderProductSerializer(order_products, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

def export_order_products(request):
    # Получаем все записи с нужной сортировкой и заранее выбираем связанные объекты:
    order_products = OrderProduct.objects.select_related(
        'order',
        'product',
        'order__status',
        'order__creator',
        'order__accept_user'
    ).order_by('-order__OrderNumber', 'product__barcode')

    # Создаем книгу и активный лист
    wb = Workbook()
    ws = wb.active
    ws.title = "OrderProducts"

    # Определяем заголовки колонок
    headers = [
        'Штрихкод', 
        'Наименование', 
        'ID магазина', 
        'Номер заказа', 
        'Статус заказа', 
        'Дата создания заказа', 
        'Заказчик', 
        'Дата сборки заказа', 
        'Товаровед приемки', 
        'Дата приемки заказа', 
        'Дата приемки товара', 
        'Принято'
    ]
    ws.append(headers)

    for op in order_products:
        # Преобразуем штрихкод в число, если это возможно
        barcode = op.product.barcode
        try:
            barcode_num = int(barcode)
        except (ValueError, TypeError):
            barcode_num = barcode

        name = op.product.name

        # Преобразуем seller в число, если возможно
        try:
            shop_id = int(op.product.seller) if op.product.seller is not None else None
        except (ValueError, TypeError):
            shop_id = op.product.seller

        try:
            order_number = int(op.order.OrderNumber) if op.order.OrderNumber is not None else None
        except (ValueError, TypeError):
            order_number = op.order.OrderNumber

        order_status = op.order.status.name if op.order.status else ''

        creation_date = (
            timezone.localtime(op.order.date).strftime('%d.%m.%Y %H:%M:%S')
            if op.order.date else ''
        )
        customer = (
            f"{op.order.creator.first_name} {op.order.creator.last_name}"
            if op.order.creator else ''
        )
        assembly_date = (
            timezone.localtime(op.order.assembly_date).strftime('%d.%m.%Y %H:%M:%S')
            if op.order.assembly_date else ''
        )
        accept_user = (
            f"{op.order.accept_user.first_name} {op.order.accept_user.last_name}"
            if op.order.accept_user else ''
        )
        order_accept_date = (
            timezone.localtime(op.order.accept_date).strftime('%d.%m.%Y %H:%M:%S')
            if op.order.accept_date else ''
        )
        product_accepted_date = (
            timezone.localtime(op.accepted_date).strftime('%d.%m.%Y %H:%M:%S')
            if op.accepted_date else ''
        )
        accepted = "да" if op.accepted else "нет"

        row = [
            barcode_num,
            name,
            shop_id,
            order_number,
            order_status,
            creation_date,
            customer,
            assembly_date,
            accept_user,
            order_accept_date,
            product_accepted_date,
            accepted,
        ]
        ws.append(row)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="order_products.xlsx"'
    wb.save(response)
    return response

#Проблемные товары 1
class ProblematicProduct1ListView(generics.ListAPIView):
    """
    API эндпоинт для получения списка продуктов, которые:
    1. Находятся в статусе перемещения с ID=3.
    2. НЕ имеют связанных STRequest (через STRequestProduct) со статусом 2 или 3.
    """
    serializer_class = ProblematicProduct1Serializer
    # Подключаем фильтр для сортировки
    filter_backends = [filters.OrderingFilter]
    pagination_class = StandardResultsSetPagination
    # Указываем поля, по которым разрешена сортировка через URL параметр ?ordering=...
    # Например: ?ordering=name или ?ordering=-priority (для обратной сортировки)
    ordering_fields = ['barcode', 'name', 'income_date', 'priority', 'income_stockman__first_name']
    # Сортировка по умолчанию
    ordering = ['income_date']

    def get_queryset(self):
        """
        Переопределяем метод для получения кастомного QuerySet.
        """
        # ID статусов STRequest, которые нужно исключить
        excluded_request_status_ids = [2, 3, 5]

        # Строим запрос:
        # 1. Выбираем продукты со статусом перемещения ID=3
        # 2. Исключаем те продукты, у которых есть хотя бы одна связанная
        #    заявка STRequest (через STRequestProduct) со статусом 2 или 3.
        # 3. Используем select_related для оптимизации запроса к связанной модели User (income_stockman)
        queryset = Product.objects.filter(
            move_status_id=3  # Фильтруем по ID статуса перемещения
        ).exclude(
            # Используем обратную связь от Product к STRequestProduct (strequestproduct)
            # и далее к STRequest (request) и его статусу (status_id)
            strequestproduct__request__status_id__in=excluded_request_status_ids
        ).select_related('income_stockman') # Оптимизация для получения данных кладовщика

        # distinct() может понадобиться, если один продукт может быть связан
        # с несколькими заявками, но в данном случае exclude должен работать корректно.
        # Если возникнут дубликаты, добавьте .distinct() перед select_related()

        return queryset

#дубликаты в заявках
class ProblematicProduct2ListView(generics.ListAPIView):
    """
    API эндпоинт для получения списка продуктов, которые задублированы
    (встречаются более чем в одной) в заявках STRequest со статусом 2 или 3.
    """
    serializer_class = ProblematicProduct2Serializer
    filter_backends = [filters.OrderingFilter]
    pagination_class = StandardResultsSetPagination
    # Поля для сортировки
    ordering_fields = ['barcode', 'name', 'income_date', 'priority', 'income_stockman__first_name']
    # Сортировка по умолчанию (например, по штрихкоду)
    ordering = ['barcode']

    # Временное хранилище для карты номеров заявок (чтобы не вычислять дважды)
    _product_request_map = None

    def _build_request_map(self, product_ids):
        """
        Вспомогательный метод для создания словаря:
        { product_id: [RequestNumber1, RequestNumber2, ...], ... }
        для указанных ID продуктов и заявок со статусом 2 или 3.
        """
        # Используем defaultdict для удобного добавления в списки
        product_request_map = defaultdict(list)
        # Статусы заявок, которые нас интересуют
        relevant_status_ids = [2, 3]

        # Находим все связи продукт-заявка для нужных продуктов и статусов заявок
        relevant_links = STRequestProduct.objects.filter(
            product_id__in=product_ids,
            request__status_id__in=relevant_status_ids
        ).select_related('request') # Оптимизация: сразу получаем данные заявки

        # Заполняем словарь
        for link in relevant_links:
            if link.request: # Убедимся, что связанная заявка существует
                product_request_map[link.product_id].append(link.request.RequestNumber)

        # Преобразуем defaultdict обратно в обычный dict для чистоты (не обязательно)
        return dict(product_request_map)

    def get_queryset(self):
        """
        Возвращает QuerySet продуктов, которые присутствуют более чем в одной
        заявке STRequest со статусом 2 или 3.
        """
        # Статусы заявок, которые нас интересуют
        relevant_status_ids = [2, 3]

        # Шаг 1: Находим ID продуктов, связанных с заявками нужных статусов
        product_links = STRequestProduct.objects.filter(
            request__status_id__in=relevant_status_ids
        ).values(
            'product_id' # Группируем по ID продукта
        ).annotate(
            request_count=Count('request_id') # Считаем количество уникальных заявок для каждого продукта
                                             # Или Count('id') если нужна связь STRequestProduct
        ).filter(
            request_count__gt=1 # Оставляем только те продукты, у которых > 1 заявки
        )

        # Шаг 2: Извлекаем только ID этих продуктов
        duplicated_product_ids = product_links.values_list('product_id', flat=True)

        # Преобразуем в список для дальнейшего использования
        duplicated_product_ids_list = list(duplicated_product_ids)

        # Шаг 3: Строим карту номеров заявок для найденных продуктов
        # Сохраняем карту в атрибут экземпляра для передачи в контекст сериализатора
        self._product_request_map = self._build_request_map(duplicated_product_ids_list)

        # Шаг 4: Получаем основные объекты Product
        queryset = Product.objects.filter(
            id__in=duplicated_product_ids_list
        ).select_related('income_stockman') # Оптимизация для получения данных кладовщика

        return queryset

    def get_serializer_context(self):
        """
        Передаем предзагруженную карту номеров заявок в контекст сериализатора.
        """
        # Получаем стандартный контекст
        context = super().get_serializer_context()
        # Добавляем нашу карту
        # Убеждаемся, что get_queryset уже был вызван (DRF это гарантирует)
        # и карта была создана
        context['product_request_map'] = getattr(self, '_product_request_map', {})
        return context

#отправленные более суток назад
class ProblematicProduct3ListView(generics.ListAPIView):
    serializer_class = ProblematicProduct3Serializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['barcode', 'name', 'income_date', 'priority', 'income_stockman__first_name']
    ordering = ['income_date'] 

    def get_queryset(self):
        one_day_ago = timezone.now() - timedelta(days=1)

        has_recent_status_5_subquery = STRequest.objects.filter(
            strequestproduct__product_id=OuterRef('pk'),
            status_id=5,
            check_time__gte=one_day_ago
        )

        latest_target_strequest_base_qs = STRequest.objects.filter(
            strequestproduct__product_id=OuterRef('pk'),
            status_id=5,
            check_time__lt=one_day_ago
        ).order_by('-check_time')

        target_strequest_number_subquery = latest_target_strequest_base_qs.values('RequestNumber')[:1]
        target_strequest_check_time_subquery = latest_target_strequest_base_qs.values('check_time')[:1]
        # Аннотируем ID целевой заявки, чтобы использовать в сериализаторе
        target_strequest_id_annotation_subquery = latest_target_strequest_base_qs.values('pk')[:1]


        has_any_old_status_5_subquery = STRequest.objects.filter(
            strequestproduct__product_id=OuterRef('pk'),
            status_id=5,
            check_time__lt=one_day_ago
        )

        queryset = Product.objects.filter(
            move_status_id__in=[3, 25, 30]
        ).exclude(
            Q(strequestproduct__request__status_id__in=[2, 3])
        ).annotate(
            _has_recent_status_5=Exists(has_recent_status_5_subquery),
            _has_any_old_status_5=Exists(has_any_old_status_5_subquery)
        ).filter(
            _has_recent_status_5=False,
            _has_any_old_status_5=True
        ).annotate(
            target_strequest_number=Subquery(target_strequest_number_subquery),
            target_strequest_check_time=Subquery(target_strequest_check_time_subquery),
            # Явно аннотируем ID целевой заявки STRequest
            annotated_target_strequest_id=Subquery(target_strequest_id_annotation_subquery)
            # Убираем предыдущую аннотацию target_srp_photo_date
        ).filter(
            target_strequest_number__isnull=False # или annotated_target_strequest_id__isnull=False
        ).select_related('income_stockman', 'move_status').distinct()

        return queryset

#печать шк
class BarcodePrintView(APIView):

    def get(self, request, barcode, format=None):
        # 1. Find the product by barcode
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return Response({"error": "ШК не обнаружен в базе"}, status=status.HTTP_404_NOT_FOUND)

        # 2. Check the product's move_status
        # Allowed move_status IDs for printing are 2, 3, 25, 30
        allowed_move_status_ids = [2, 3, 25, 30]
        if not product.move_status or product.move_status.id not in allowed_move_status_ids:
            current_status_name = product.move_status.name if product.move_status else "None"
            return Response(
                {"error": f"Не разрешена печать с этим статусом (текущий статус: '{current_status_name}')"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. If checks are passed, create a new ProductOperation record
        try:
            # Assuming ProductOperationType with id=7 is for "Barcode Print"
            print_operation_type = ProductOperationTypes.objects.get(id=7)
        except ProductOperationTypes.DoesNotExist:
            # This indicates a server configuration issue
            return Response(
                {"error": "Тип операции для печати штрихкода (id=7) не настроен в системе."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        ProductOperation.objects.create(
            product=product,
            user=request.user,
            operation_type=print_operation_type
            # 'date' field in ProductOperation will be set automatically due to auto_now_add=True
        )

        # Prepare the successful response data
        response_data = {
            "Barcode": product.barcode,
            "name": product.name,
            "move_status": product.move_status.name # Assumes move_status is not None here due to earlier check
        }

        return Response(response_data, status=status.HTTP_200_OK)

#Определение типа заявки STRequestType
def determine_and_set_strequest_type(request_number):
    try:
        st_req = STRequest.objects.get(RequestNumber=request_number)
    except STRequest.DoesNotExist:
        return None

    # получаем все id типов заявок из категорий продуктов
    type_ids = list(
        STRequestProduct.objects
        .filter(request=st_req)
        .values_list('product__category__STRequestType_id', flat=True)
    )
    # убираем пустые
    type_ids = [tid for tid in type_ids if tid is not None]
    if not type_ids:
        return None

    counts = Counter(type_ids)
    max_count = max(counts.values())
    # все типы с макс. количеством
    candidates = [tid for tid, cnt in counts.items() if cnt == max_count]
    # порядок приоритета: минимальный id (1,2,3,…)
    chosen_id = sorted(candidates)[0]

    # если отличается — сохраняем
    if st_req.STRequestType_id != chosen_id:
        st_req.STRequestType_id = chosen_id
        st_req.save(update_fields=['STRequestType'])

    # возвращаем сам объект STRequestType
    return STRequestType.objects.get(pk=chosen_id)

#Вручную меняем STRequestType и блокируем
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_set_strequest_type(request, RequestNumber, strequest_type_id):
    """
    Ручная установка STRequestType для заявки.
    URL: /<RequestNumber>/<strequest_type_id>/
    Меняет поле STRequestType и ставит STRequestTypeBlocked=True.
    """
    # 1) Находим заявку
    try:
        st_req = STRequest.objects.get(RequestNumber=RequestNumber)
    except STRequest.DoesNotExist:
        return Response({"error": "Заявка не найдена"}, status=404)

    # 2) Находим нужный тип
    try:
        new_type = STRequestType.objects.get(pk=strequest_type_id)
    except STRequestType.DoesNotExist:
        return Response({"error": "Тип заявки не найден"}, status=404)

    # 3) Проставляем и сохраняем
    st_req.STRequestType = new_type
    st_req.STRequestTypeBlocked = True
    st_req.save(update_fields=['STRequestType', 'STRequestTypeBlocked'])

    # 4) Возвращаем новый статус
    return Response({
        "RequestNumber": st_req.RequestNumber,
        "STRequestType": new_type.id,
        "STRequestTypeBlocked": st_req.STRequestTypeBlocked
    })
