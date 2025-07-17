from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.filters import OrderingFilter
from django.db.models import Count, Q, ExpressionWrapper, F, DurationField, Sum
from django_filters.rest_framework import DjangoFilterBackend
from django_q.tasks import async_task
from datetime import datetime, time
from core.models import (
    Order,
    OrderProduct,
    OrderStatus,
    Product,
    ProductMoveStatus,
    STRequest,
    STRequestProduct,
    STRequestStatus,
    STRequestHistory,
    STRequestHistoryOperations,
    ProductOperationTypes,
    ProductOperation,
    Invoice,
    InvoiceProduct
    )
from .serializers import (
    OrderSerializer,
    OrderStatusSerializer,
    OrderDetailSerializer,
    )
from .pagination import StandardResultsSetPagination

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

#начало сборки заказа
class OrderStartAssemblyView(APIView):
    def post(self, request, order_number):
        # Ищем заказ по OrderNumber
        order = get_object_or_404(Order, OrderNumber=order_number)
        
        # Проверяем, находится ли заказ в статусе 2 или 3
        if order.status.id not in [2, 3]:
            return Response(
                {"error": f"неверный статус заказа - {order.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Обновляем поля заказа
        order.status = OrderStatus.objects.get(id=3)
        order.assembly_date = timezone.now()
        order.save()
        
        # Получаем количество товаров в заказе через модель OrderProduct
        count = order.orderproduct_set.count()
        
        # Отправляем сообщение в указанный Telegram чат
        telegram_chat_id = '-1002559221974'
        OKZ_THREAD_ID = 8
        message_text = (
            f"Начат сбор заказа №{order.OrderNumber}\n"
            f"Количество товаров - {count}"
        )
        async_task(
            'telegram_bot.tasks.send_message_task', # Путь к нашей функции
            chat_id=telegram_chat_id,
            text=message_text,
            message_thread_id=OKZ_THREAD_ID
        )
        
        return Response(
            {"message": "Сбор начат успешно."},
            status=status.HTTP_200_OK
        )

class OrderStatsView(APIView):
    def get(self, request, format=None):
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')

        if not date_from_str or not date_to_str:
            return Response(
                {"error": "Параметры 'date_from' и 'date_to' обязательны."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Преобразуем строки в datetime объекты
            dt_from = datetime.strptime(date_from_str, "%d.%m.%Y")
            dt_to = datetime.strptime(date_to_str, "%d.%m.%Y")
            
            # Устанавливаем время для полного охвата дней
            start_date = datetime.combine(dt_from, time.min)
            end_date = datetime.combine(dt_to, time.max)

        except ValueError:
            return Response(
                {"error": "Неверный формат даты. Используйте ДД.ММ.ГГГГ."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Фильтруем заказы по диапазону дат
        orders = Order.objects.filter(date__gte=start_date, date__lte=end_date)
        
        # Считаем количество заказов
        order_count = orders.count()
        
        # Считаем общее количество SKU (товарных позиций) в этих заказах
        sku_count = OrderProduct.objects.filter(order__in=orders).count()

        return Response({
            "order_count": order_count,
            "sku_count": sku_count
        })
