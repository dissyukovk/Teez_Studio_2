from django.shortcuts import render, redirect, get_object_or_404
from .models import STRequest, Product, Invoice, ProductMoveStatus, ProductCategory, Product, Order, OrderProduct, OrderStatus, STRequestProduct, ProductOperation, ProductOperationTypes, InvoiceProduct, RetouchStatus, STRequestStatus, UserURLs, STRequestHistory, STRequestHistoryOperations, Blocked_Shops, Nofoto, Blocked_Barcode, APIKeys, UserProfile
from .forms import STRequestForm
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, status, serializers, generics, permissions, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import NotFound
from django.contrib.auth.models import User, Group
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.conf import settings
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import UserSerializer, ProductSerializer, STRequestSerializer, InvoiceSerializer, StatusSerializer, ProductOperationSerializer, OrderSerializer, RetouchStatusSerializer, STRequestStatusSerializer, OrderStatusSerializer, ProductCategorySerializer, UserURLsSerializer, STRequestHistorySerializer, NofotoListSerializer, DefectSerializer
from .pagination import NofotoPagination
from django.db import transaction, IntegrityError
from django.db.models import Count, Max, F, Value, Q, Sum, OuterRef, Subquery
from django.db.models.functions import Concat
from django.http import JsonResponse
from django.utils import timezone
import logging
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
from django_q.tasks import async_task


# Настраиваем логирование
logger = logging.getLogger(__name__)

# Пагинация
class ProductPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 999999

class OrderPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000

class ProductHistoryPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000

class CategoryPagination(PageNumberPagination):
    page_size = 100  # Default page size
    page_size_query_param = 'page_size'
    max_page_size = 999999  # Max page size for user

# CRUD для пользователей (User) с фильтрацией и сортировкой
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['id', 'first_name', 'last_name', 'email', 'groups__name']
    ordering_fields = ['id', 'first_name', 'last_name', 'email']

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_data = {
            'id': user.id,  # Add the user's ID here
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'groups': [group.name for group in user.groups.all()]
        }
        return Response(user_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_products(request):
    barcodes = request.data.get('barcodes', [])
    user_id = request.data.get('userId')
    status_id = request.data.get('status')
    date = request.data.get('date', timezone.now())

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    for barcode in barcodes:
        try:
            product = Product.objects.get(barcode=barcode)
            product.move_status_id = status_id  # Присваиваем новый статус
            product.income_stockman_id = user_id  # Записываем товароведа приемки
            product.income_date = date  # Записываем дату приемки
            product.save()

            # Логируем операцию
            ProductOperation.objects.create(
                product=product,
                operation_type_id=3,  # Тип операции "income"
                user=user,
                date=date
            )
        except Product.DoesNotExist:
            continue

    return Response({'message': 'Products accepted successfully'}, status=200)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_products(request):
    barcodes = request.data.get('barcodes', [])
    user_id = request.data.get('userId')
    status_id = request.data.get('status')
    date = request.data.get('date', timezone.now())

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    for barcode in barcodes:
        try:
            product = Product.objects.get(barcode=barcode)
            product.move_status_id = status_id  # Присваиваем новый статус
            product.outcome_stockman_id = user_id  # Записываем товароведа отправки
            product.outcome_date = date  # Записываем дату отправки
            product.save()

            # Логируем операцию
            ProductOperation.objects.create(
                product=product,
                operation_type_id=4,  # Тип операции "outcome"
                user=user,
                date=date
            )
        except Product.DoesNotExist:
            continue

    return Response({'message': 'Products sent successfully'}, status=200)


def generate_next_request_number():
    with transaction.atomic():
        last_request = STRequest.objects.select_for_update().order_by('-RequestNumber').first()
        if last_request:
            # Увеличиваем числовую часть номера
            next_number = str(int(last_request.RequestNumber) + 1).zfill(13)
        else:
            next_number = "2000000000001"
        return next_number

# Проверка наличия штрихкода
@api_view(['GET'])
def check_barcode(request, barcode):
    try:
        product = Product.objects.get(barcode=barcode)
        return Response({'exists': True}, status=status.HTTP_200_OK)
    except Product.DoesNotExist:
        return Response({'exists': False}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_product_operation(request):
    user = request.user
    barcodes = request.data.get('barcodes', [])
    operation_id = request.data.get('operation', '')
    comment = request.data.get('comment', '')  # Получаем комментарий из запроса

    # Находим тип операции
    operation_type = ProductOperationTypes.objects.filter(id=operation_id).first()
    if not operation_type:
        return Response({'error': 'Invalid operation type'}, status=400)

    for barcode in barcodes:
        product = Product.objects.filter(barcode=barcode).first()
        if product:
            ProductOperation.objects.create(
                product=product,
                operation_type=operation_type,  # Передаем объект типа операции
                user=user,
                date=timezone.now(),
                comment=comment  # Сохраняем комментарий
            )

    return Response({'message': 'Операция успешно добавлена в историю'})

# Получение информации о заказе по штрихкоду
@api_view(['GET'])
def get_order_for_barcode(request, barcode):
    try:
        # Найдем продукт по штрихкоду
        product = Product.objects.filter(barcode=barcode).first()

        if product:
            # Ищем заказ через связь OrderProduct
            order_product = OrderProduct.objects.filter(product=product).first()
            
            if order_product:
                order = order_product.order  # Получаем заказ, связанный с продуктом
                order_data = {
                    "orderNumber": order.OrderNumber,
                    "isComplete": order_product.order.status_id in [8, 9]  # Проверяем статус заказа
                }
                return Response(order_data, status=status.HTTP_200_OK)
            else:
                return Response({"orderNumber": "Нет заказа"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Штрихкод не найден"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
# CRUD для STRequest
class STRequestViewSet(viewsets.ModelViewSet):
    queryset = STRequest.objects.all()
    serializer_class = STRequestSerializer


# CRUD для Invoice
class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer


# Функция для вывода пользователей с фильтрацией и пагинацией
@api_view(['GET'])
def user_list(request):
    users = User.objects.all()

    # Фильтрация по полям
    first_name = request.query_params.get('first_name', None)
    last_name = request.query_params.get('last_name', None)
    group = request.query_params.get('group', None)

    if first_name:
        users = users.filter(first_name__icontains=first_name)
    if last_name:
        users = users.filter(last_name__icontains=last_name)
    if group:
        users = users.filter(groups__name__icontains=group)

    # Сортировка
    sort_field = request.query_params.get('sort_field', None)
    sort_order = request.query_params.get('sort_order', 'asc')

    if sort_field:
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        users = users.order_by(sort_field)

    # Пагинация
    paginator = ProductPagination()
    paginated_users = paginator.paginate_queryset(users, request)
    serializer = UserSerializer(paginated_users, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
def product_list(request):
    products = Product.objects.select_related('category', 'move_status').annotate(
        request_number=Subquery(
            STRequestProduct.objects.filter(product=OuterRef('pk'))
            .order_by('-id')
            .values('request__RequestNumber')[:1]
        )
    )

    # Get filtering parameters
    barcode = request.query_params.get('barcode', None)
    name = request.query_params.get('name', None)
    category = request.query_params.get('category', None)
    move_status_id = request.query_params.get('move_status_id', None)
    move_status_ids = request.query_params.getlist('move_status_id__in')

    # Filter out empty strings from move_status_ids
    move_status_ids = [int(status_id) for status_id in move_status_ids if status_id]

    # Apply filters
    if move_status_ids:
        products = products.filter(move_status_id__in=move_status_ids)
    elif move_status_id:
        products = products.filter(move_status_id=move_status_id)

    if barcode:
        products = products.filter(barcode__icontains=barcode)
    if name:
        products = products.filter(name__icontains=name)
    if category:
        products = products.filter(category__name__icontains=category)

    # Sorting
    sort_field = request.query_params.get('sort_field', None)
    sort_order = request.query_params.get('sort_order', 'asc')

    if sort_field:
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        products = products.order_by(sort_field)

    # Pagination
    paginator = ProductPagination()
    paginated_products = paginator.paginate_queryset(products, request)
    product_serializer = ProductSerializer(paginated_products, many=True)

    # Retrieve and serialize the latest request and invoice
    latest_request = STRequest.objects.order_by('-creation_date').first()
    latest_invoice = Invoice.objects.order_by('-date').first()

    latest_request_data = STRequestSerializer(latest_request).data if latest_request else None
    latest_invoice_data = InvoiceSerializer(latest_invoice).data if latest_invoice else None

    # Include the serialized data in the response
    response_data = {
        'products': product_serializer.data,
        'latest_request': latest_request_data,
        'latest_invoice': latest_invoice_data
    }
    
    return paginator.get_paginated_response(response_data)

# Фильтрация для STRequest
@api_view(['GET'])
def strequest_list(request):
    strequests = STRequest.objects.select_related('stockman', 'status').all()  # Предзагрузка stockman и status
    
    # Фильтрация по статусу
    status = request.query_params.get('status', None)
    if status:
        strequests = strequests.filter(status__id=status)

    # Фильтрация по фотографу
    photographer_id = request.query_params.get('photographer', None)
    if photographer_id:
        strequests = strequests.filter(photographer_id=photographer_id)
    
    # Фильтрация по ретушеру
    retoucher_id = request.query_params.get('retoucher', None)
    if retoucher_id:
        strequests = strequests.filter(retoucher_id=retoucher_id)
    
    # Дополнительные фильтры
    RequestNumber = request.query_params.get('RequestNumber', None)
    stockman = request.query_params.get('stockman', None)
    barcode = request.query_params.get('barcode', None)
    product_name = request.query_params.get('productName', None)  # Новый параметр для наименования продукта

    if RequestNumber:
        strequests = strequests.filter(RequestNumber__icontains=RequestNumber)
    if stockman:
        strequests = strequests.filter(stockman__username__icontains=stockman)
    if barcode:
        strequests = strequests.filter(strequestproduct__product__barcode__icontains=barcode)
    if product_name:
        strequests = strequests.filter(strequestproduct__product__name__icontains=product_name)  # Фильтрация по наименованию продукта

    # Сортировка
    sort_field = request.query_params.get('sort_field', 'RequestNumber')
    sort_order = request.query_params.get('sort_order', 'asc')

    if sort_field:
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        strequests = strequests.order_by(sort_field)

    paginator = ProductPagination()
    paginated_strequests = paginator.paginate_queryset(strequests, request)
    serializer = STRequestSerializer(paginated_strequests, many=True)
    return paginator.get_paginated_response(serializer.data)

# Фильтрация для Invoice с пагинацией и фильтрацией по штрихкоду товара
@api_view(['GET'])
def invoice_list(request):
    invoices = Invoice.objects.all()

    # Фильтрация по полям
    invoice_number = request.query_params.get('invoice_number', None)
    barcode = request.query_params.get('barcode', None)

    if invoice_number:
        invoices = invoices.filter(InvoiceNumber__icontains=invoice_number)
    if barcode:
        # Фильтрация по продуктам, связанным с накладными
        invoices = invoices.filter(invoiceproduct__product__barcode__icontains=barcode)

    # Сортировка
    sort_field = request.query_params.get('sort_field', None)
    sort_order = request.query_params.get('sort_order', 'asc')

    if sort_field:
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        invoices = invoices.order_by(sort_field)

    paginator = ProductPagination()
    paginated_invoices = paginator.paginate_queryset(invoices, request)
    serializer = InvoiceSerializer(paginated_invoices, many=True)
    return paginator.get_paginated_response(serializer.data)

# Фильтрация для Invoice с пагинацией
class InvoiceListView(ListAPIView):
    queryset = Invoice.objects.all().order_by('id')
    serializer_class = InvoiceSerializer
    pagination_class = ProductPagination

    def filter_queryset(self, queryset):
        invoice_number = self.request.query_params.get('invoice_number', None)
        creator = self.request.query_params.get('creator', None)
        date = self.request.query_params.get('date', None)

        if invoice_number:
            queryset = queryset.filter(InvoiceNumber__icontains=invoice_number)
        if creator:
            queryset = queryset.filter(creator__username__icontains=creator)
        if date:
            queryset = queryset.filter(date__date=date)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Bulk Upload Products
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_upload_products(request):
    data = request.data.get('data', [])

    for row in data:
        try:
            barcode = row['barcode']
            name = row['name']
            category_id = row['category_id']
            seller = row['seller']
            in_stock_sum = row['in_stock_sum']
            cell = row['cell']

            product, created = Product.objects.get_or_create(
                barcode=barcode,
                defaults={
                    'name': name,
                    'category_id': category_id,
                    'seller': seller,
                    'in_stock_sum': in_stock_sum,
                    'cell': cell,
                }
            )
            if not created:
                product.name = name
                product.category_id = category_id
                product.seller = seller
                product.in_stock_sum = in_stock_sum
                product.cell = cell
                product.save()

        except Exception as e:
            return Response({'error': str(e)}, status=400)

    return Response({'message': 'Данные успешно внесены!'}, status=200)


# Отображение статусов
class StatusesListView(APIView):
    def get(self, request):
        statuses = ProductMoveStatus.objects.all()
        serializer = StatusSerializer(statuses, many=True)
        return Response(serializer.data)


# Получение списка заявок в зависимости от роли (оставим без изменений)
@login_required
def get_requests(request):
    user = request.user
    if user.groups.filter(name='товаровед').exists() or user.groups.filter(name='менеджер').exists():
        requests = STRequest.objects.all()
    elif user.groups.filter(name='старший фотограф').exists():
        requests = STRequest.objects.filter(status__name__in=['Создана', 'на съемке', 'на проверке'])
    elif user.groups.filter(name='фотограф').exists():
        requests = STRequest.objects.filter(photographer=user, status__name='на съемке')
    elif user.groups.filter(name='старший ретушер').exists():
        requests = STRequest.objects.filter(status__name__in=['Отснято', 'на ретуши', 'на проверке ретуши'])
    elif user.groups.filter(name='ретушер').exists():
        requests = STRequest.objects.filter(retoucher=user, status__name='на ретуши')
    else:
        requests = STRequest.objects.none()  # Пустой QuerySet, если пользователь не имеет роли

    return render(request, 'core/requests_list.html', {'requests': requests})

# Создание и редактирование заявок
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_request(request):
    barcodes = request.data.get('barcodes', [])
    user = request.user

    # Получаем последнюю заявку
    last_request = STRequest.objects.order_by('id').last()
    
    # Генерируем новый номер заявки
    if last_request:
        last_request_number = int(last_request.RequestNumber)
        new_request_number = str(last_request_number + 1).zfill(13)
    else:
        new_request_number = "2000000000001"

    # Создаем новую заявку
    new_request = STRequest.objects.create(
        RequestNumber=new_request_number,
        creation_date=timezone.now(),
        stockman=user,
        status_id=2
    )

    # Получаем тип операции для истории
    operation_type = STRequestHistoryOperations.objects.filter(id=1).first()
    if not operation_type:
        return Response({'error': 'Тип операции с ID=1 не найден'}, status=400)

    # Связываем товары с заявкой и сохраняем историю
    for barcode in barcodes:  # Ожидаем, что `barcodes` содержит список строк
        product = Product.objects.filter(barcode=barcode).first()
        if product:
            # Создаем связь товара с заявкой
            STRequestProduct.objects.create(request=new_request, product=product)

            # Сохраняем в историю операций
            STRequestHistory.objects.create(
                st_request=new_request,
                product=product,
                user=user,
                date=timezone.now(),
                operation=operation_type
            )

    # Возвращаем ответ с созданной заявкой
    return Response({'status': 'Заявка создана', 'requestNumber': new_request_number})

@login_required
def update_request(request, pk):
    st_request = get_object_or_404(STRequest, pk=pk)
    if request.method == 'POST':
        form = STRequestForm(request.POST, instance=st_request)
        if form.is_valid():
            form.save()
            return redirect('requests_list')
    else:
        form = STRequestForm(instance=st_request)
    return render(request, 'core/update_request.html', {'form': form})

# View для просмотра с фильтрацией и пагинацией
class ProductOperationListView(ListAPIView):
    queryset = ProductOperation.objects.all()
    serializer_class = ProductOperationSerializer
    pagination_class = ProductPagination

    # Фильтрация по штрихкоду, дате, пользователю и операции
    def get_queryset(self):
        queryset = super().get_queryset()
        barcode = self.request.query_params.get('barcode', None)
        operation = self.request.query_params.get('operation', None)
        user_id = self.request.query_params.get('user', None)
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)

        if barcode:
            queryset = queryset.filter(product__barcode=barcode)
        if operation:
            queryset = queryset.filter(operation=operation)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if date_from and date_to:
            queryset = queryset.filter(date__range=[date_from, date_to])
        elif date_from:
            queryset = queryset.filter(date__gte=date_from)
        elif date_to:
            queryset = queryset.filter(date__lte=date_to)

        return queryset

# ViewSet для CRUD операций (создание, чтение, обновление, удаление)
class ProductOperationCRUDViewSet(viewsets.ModelViewSet):
    queryset = ProductOperation.objects.all()
    serializer_class = ProductOperationSerializer

class OrderListView(ListAPIView):
    queryset = Order.objects.all().select_related('creator', 'status').annotate(
        total_products=Count('orderproduct')  # Обратная связь через orderproduct
    )
    serializer_class = OrderSerializer
    pagination_class = OrderPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['OrderNumber', 'creator__username', 'status']
    ordering_fields = ['OrderNumber', 'date', 'status', 'creator__username']
    ordering = ['date']

class RetouchStatusListView(APIView):
    permission_classes = [IsAuthenticated]  # Ограничиваем доступ только для авторизованных пользователей

    def get(self, request):
        retouch_statuses = RetouchStatus.objects.all()
        serializer = RetouchStatusSerializer(retouch_statuses, many=True)
        return Response(serializer.data)

@api_view(['GET'])
def get_last_request(request, barcode):
    try:
        # Находим продукт по штрихкоду
        product = Product.objects.get(barcode=barcode)
        
        # Используем связанный объект 'strequestproduct' для поиска последней заявки по продукту
        last_request = STRequest.objects.filter(strequestproduct__product=product).order_by('-creation_date').first()

        if last_request:
            status_id = last_request.status.id
            status_name = last_request.status.name  # Получаем название статуса
            
            return Response({
                'requestNumber': last_request.RequestNumber,
                'statusName': status_name  # Возвращаем название статуса
            })
        else:
            # Если заявок с продуктом нет
            return Response({
                'requestNumber': None,
                'statusName': 'Нет заявок'
            }, status=200)
        
    except Product.DoesNotExist:
        return Response({'error': 'Продукт не найден'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_product_statuses(request):
    barcodes = request.data.get('barcodes', [])
    status_id = request.data.get('status', None)  # Числовое значение статуса
    user_id = request.data.get('userId', None)    # Числовое значение ID пользователя
    date = request.data.get('date', timezone.now())  # Дата, если не передана

    if not all([barcodes, status_id, user_id]):
        return Response({'error': 'Missing required fields'}, status=400)

    # Получаем пользователя
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    # Обрабатываем каждый штрихкод
    for barcode in barcodes:
        try:
            product = Product.objects.get(barcode=barcode)
            product.move_status_id = status_id
            product.income_stockman_id = user_id if status_id == 3 else None  # Если приемка, записываем товароведа приемки
            product.outcome_stockman_id = user_id if status_id == 4 else None  # Если отправка, записываем товароведа отправки
            product.income_date = date if status_id == 3 else None
            product.outcome_date = date if status_id == 4 else None
            product.save()
        except Product.DoesNotExist:
            continue  # Пропускаем штрихкоды, если продукт не найден

    return Response({'message': 'Product statuses updated successfully'}, status=200)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_invoice(request):
    barcodes = request.data.get('barcodes', [])
    creator = request.user  # Получаем текущего пользователя
    date = request.data.get('date', timezone.now())

    # Получаем максимальный номер накладной и увеличиваем его на 1
    max_invoice_number = Invoice.objects.aggregate(Max('InvoiceNumber'))['InvoiceNumber__max']
    new_invoice_number = str(int(max_invoice_number) + 1).zfill(13) if max_invoice_number else '0000000000001'

    # Создаем новую накладную с уникальным номером
    new_invoice = Invoice.objects.create(
        InvoiceNumber=new_invoice_number,
        date=date,
        creator=creator
    )

    # Добавляем товары в накладную
    for barcode in barcodes:
        try:
            product = Product.objects.get(barcode=barcode)
            InvoiceProduct.objects.create(invoice=new_invoice, product=product)
        except Product.DoesNotExist:
            continue

    return Response({'invoiceNumber': new_invoice.InvoiceNumber, 'status': 'Накладная создана'}, status=201)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_defective(request):
    barcode = request.data.get('barcode')
    comment = request.data.get('comment', '')
    user = request.user

    try:
        product = Product.objects.get(barcode=barcode)
        product.move_status_id = 25  # Статус "брак"
        product.save()

        # Логирование операции
        ProductOperation.objects.create(
            product=product,
            operation_type_id=25,  # ID операции "брак"
            user=user,
            comment=comment
        )
        return Response({'message': 'Товар помечен как брак'}, status=200)
    except Product.DoesNotExist:
        return Response({'error': 'Товар не найден'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_product_by_barcode(request, barcode):
    try:
        product = Product.objects.get(barcode=barcode)
        # Ищем последнюю активную заявку на продукт
        last_request = STRequest.objects.filter(strequestproduct__product=product).order_by('-creation_date').first()

        # Если заявка найдена, получаем номер заявки и статус
        if last_request:
            last_request_data = {
                'request_number': last_request.RequestNumber,
                'request_status': last_request.status.name
            }
        else:
            # Если заявок нет, возвращаем сообщение
            last_request_data = {
                'request_number': None,
                'request_status': 'Нет заявок'
            }

        # Серилизуем продукт
        product_data = ProductSerializer(product).data
        product_data['last_request'] = last_request_data  # Добавляем данные о последней заявке

        return Response(product_data)

    except Product.DoesNotExist:
        return Response({'error': 'Продукт не найден'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_defect_operation(request):
    barcode = request.data.get('barcode', None)
    user_id = request.data.get('userId', None)
    comment = request.data.get('comment', '')

    if not barcode or not user_id:
        return Response({'error': 'Barcode and userId are required'}, status=400)

    # Получаем пользователя
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    # Получаем продукт
    try:
        product = Product.objects.get(barcode=barcode)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)

    # Обновляем статус продукта на "брак" (25)
    product.move_status_id = 25
    product.save()

    # Получаем тип операции (25 - "брак")
    defect_operation_type = ProductOperationTypes.objects.get(id=25)

    # Логируем операцию с комментарием
    ProductOperation.objects.create(
        product=product,
        operation_type=defect_operation_type,
        user=user,
        comment=comment,  # Сохраняем комментарий
        date=timezone.now()
    )

    return Response({'message': 'Product marked as defective, status updated, and logged successfully'}, status=200)

@api_view(['POST'])
def create_draft_request(request):
    user = request.user
    try:
        with transaction.atomic():
            # Генерируем новый номер заявки
            request_number = generate_next_request_number()

            # Проверяем, существует ли уже такая заявка
            if STRequest.objects.filter(RequestNumber=request_number).exists():
                raise IntegrityError(f"Request number {request_number} already exists.")
            
            # Создаем новую заявку
            new_request = STRequest.objects.create(
                RequestNumber=request_number,
                stockman=user,
                creation_date=timezone.now(),
                status_id=1  # Статус черновика
            )
        return Response({'requestNumber': new_request.RequestNumber}, status=200)
    
    except IntegrityError as e:
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
def finalize_request(request):
    # Финализация заявки: привязываем штрихкоды и переводим статус в 2
    request_number = request.data.get('requestNumber')
    barcodes = request.data.get('barcodes', [])

    st_request = STRequest.objects.filter(RequestNumber=request_number).first()
    if not st_request:
        return Response({'error': 'Заявка не найдена'}, status=404)

    # Получаем тип операции для истории
    operation_type = STRequestHistoryOperations.objects.filter(id=1).first()
    if not operation_type:
        return Response({'error': 'Тип операции с ID=1 не найден'}, status=400)

    for barcode in barcodes:
        product = Product.objects.filter(barcode=barcode).first()
        if product:
            # Связываем товар с заявкой
            STRequestProduct.objects.create(request=st_request, product=product)

            # Сохраняем в историю операций
            STRequestHistory.objects.create(
                st_request=st_request,
                product=product,
                user=request.user,
                date=timezone.now(),
                operation=operation_type
            )

    # Переводим заявку в статус 2
    st_request.status_id = 2
    st_request.save()

    return Response({'message': 'Заявка успешно завершена'})

@api_view(['GET'])
def order_list(request):
    orders = Order.objects.all()

    # Filtering by order number
    order_number = request.query_params.get('OrderNumber', None)
    if order_number:
        orders = orders.filter(OrderNumber__icontains=order_number)

    # Filtering by product barcode
    barcode = request.query_params.get('barcode', None)
    if barcode:
        orders = orders.filter(orderproduct__product__barcode__icontains=barcode)

    # Filtering by status
    status_id = request.query_params.get('status', None)
    if status_id:
        status_ids = [int(s) for s in status_id.split(',') if s.isdigit()]
        orders = orders.filter(status_id__in=status_ids)

    # Sorting
    sort_field = request.query_params.get('sort_field', 'OrderNumber')
    sort_order = request.query_params.get('sort_order', 'asc')
    if sort_field:
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        orders = orders.order_by(sort_field)

    # Pagination
    paginator = ProductPagination()
    paginated_orders = paginator.paginate_queryset(orders, request)

    # Serializing the paginated orders
    serializer = OrderSerializer(paginated_orders, many=True)
    return paginator.get_paginated_response(serializer.data)

@api_view(['GET'])
def request_details(request, request_number):
    try:
        strequest = STRequest.objects.get(RequestNumber=request_number)
        barcodes = strequest.strequestproduct_set.all()
        
        # Добавляем категорию и ссылку на категорию в данные штрихкодов
        barcodes_data = [
            {
                'barcode': bp.product.barcode,
                'name': bp.product.name,
                'movementStatus': bp.product.move_status.name if bp.product.move_status else 'N/A',  # Проверка на None
                'category_name': bp.product.category.name if bp.product.category else 'N/A',  # Проверяем наличие категории
                'category_reference_link': bp.product.category.reference_link if bp.product.category else 'N/A',  # Проверяем наличие ссылки
                'retouch_status_name': bp.retouch_status.name if bp.retouch_status else 'N/A',  # Статус ретуши из strequestproduct
                'retouch_link': bp.product.retouch_link if bp.product.retouch_link else ''  # Ссылка на обработанные фото из Product
            }
            for bp in barcodes
        ]
        
        # Добавляем данные о фотографе
        photographer_first_name = strequest.photographer.first_name if strequest.photographer else "Не назначен"
        photographer_last_name = strequest.photographer.last_name if strequest.photographer else ""
        photographer_id = strequest.photographer.id if strequest.photographer else None

        # Добавляем данные о ретушере
        retoucher_first_name = strequest.retoucher.first_name if strequest.retoucher else "Не назначен"
        retoucher_last_name = strequest.retoucher.last_name if strequest.retoucher else ""
        retoucher_id = strequest.retoucher.id if strequest.retoucher else None
        
        return Response({
            'barcodes': barcodes_data,
            'status': strequest.status.name,
            'photographer_first_name': photographer_first_name,
            'photographer_last_name': photographer_last_name,
            'photographer_id': photographer_id,
            'retoucher_first_name': retoucher_first_name,  # Имя ретушера
            'retoucher_last_name': retoucher_last_name,    # Фамилия ретушера
            'retoucher_id': retoucher_id,                  # ID ретушера
            'comment': strequest.s_ph_comment,
            's_ph_comment': strequest.s_ph_comment,  # Комментарий фотографа
            'sr_comment': strequest.sr_comment,      # Комментарий ретушера
            'photos_link': strequest.photos_link
        })
    except STRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=404)

@api_view(['GET'])
def barcode_details(request, barcode):
    try:
        product = Product.objects.get(barcode=barcode)
        return Response({
            'exists': True,
            'name': product.name,
            'movementStatus': product.move_status.name,
            'status_id': product.move_status.id  # Добавляем ID статуса
        })
    except Product.DoesNotExist:
        return Response({'exists': False}, status=404)


@api_view(['POST'])
def update_request(request, request_number):
    added_barcodes = request.data.get('addedBarcodes', [])
    removed_barcodes = request.data.get('removedBarcodes', [])

    logger.info(f'Request data: {request.data}')  # Логируем данные, которые приходят с фронта

    try:
        strequest = STRequest.objects.get(RequestNumber=request_number)

        # Логируем штрихкоды для добавления и удаления
        logger.info(f'Добавляем штрихкоды: {added_barcodes}')
        logger.info(f'Удаляем штрихкоды: {removed_barcodes}')

        # Получаем типы операций
        add_operation = STRequestHistoryOperations.objects.filter(id=1).first()
        remove_operation = STRequestHistoryOperations.objects.filter(id=2).first()
        if not add_operation or not remove_operation:
            return Response({'error': 'Не найдены типы операций (id=1 или id=2)'}, status=400)

        # Обрабатываем удаление штрихкодов
        if removed_barcodes:
            for barcode in removed_barcodes:
                # Удаляем связь товара с заявкой
                product_relation = STRequestProduct.objects.filter(request=strequest, product__barcode=barcode).first()
                if product_relation:
                    product = product_relation.product
                    product_relation.delete()

                    # Сохраняем операцию удаления в историю
                    STRequestHistory.objects.create(
                        st_request=strequest,
                        product=product,
                        user=request.user,
                        date=timezone.now(),
                        operation=remove_operation
                    )
                    logger.info(f'Удалён штрихкод {barcode} из заявки {request_number}')

        # Обрабатываем добавление штрихкодов
        if added_barcodes:
            for barcode in added_barcodes:
                product = Product.objects.get(barcode=barcode)
                STRequestProduct.objects.create(request=strequest, product=product)

                # Сохраняем операцию добавления в историю
                STRequestHistory.objects.create(
                    st_request=strequest,
                    product=product,
                    user=request.user,
                    date=timezone.now(),
                    operation=add_operation
                )
                logger.info(f'Добавлен штрихкод {barcode} в заявку {request_number}')

        return Response({'message': 'Request updated successfully'})

    except STRequest.DoesNotExist:
        logger.error(f'Заявка с номером {request_number} не найдена')
        return Response({'error': 'Request not found'}, status=404)
    except Product.DoesNotExist:
        logger.error('Продукт с указанным штрихкодом не найден')
        return Response({'error': 'Product not found'}, status=404)
    except Exception as e:
        logger.error(f'Ошибка при обновлении заявки: {str(e)}')
        return Response({'error': 'Ошибка при обновлении заявки'}, status=500)

@api_view(['POST'])
def update_request_status(request, request_number):
    try:
        strequest = STRequest.objects.get(RequestNumber=request_number)
        
        # Обновляем статус заявки, если он передан
        status = request.data.get('status')
        if status:
            strequest.status_id = status
        
        # Обновляем photos_link только если он передан в запросе
        photos_link = request.data.get('photos_link')
        if photos_link:
            strequest.photos_link = photos_link
        
        strequest.save()
        
        return Response({'message': 'Статус и ссылка обновлены (если переданы)'}, status=200)
    except STRequest.DoesNotExist:
        return Response({'error': 'Request not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_photographers(request):
    try:
        # Ищем группу "Фотограф"
        photographers_group = Group.objects.get(name="Фотограф")
        # Получаем всех пользователей, принадлежащих этой группе
        photographers = User.objects.filter(groups=photographers_group)
        
        # Формируем список фотографов для ответа
        photographers_data = [
            {
                'id': photographer.id,
                'first_name': photographer.first_name,
                'last_name': photographer.last_name,
                'email': photographer.email
            }
            for photographer in photographers
        ]
        
        return Response(photographers_data, status=200)

    except Group.DoesNotExist:
        return Response({'error': 'Группа "Фотограф" не найдена'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_photographer(request, request_number):
    try:
        # Получаем заявку по номеру
        st_request = STRequest.objects.get(RequestNumber=request_number)
        
        # Получаем ID фотографа и комментарий из тела запроса
        photographer_id = request.data.get('photographer_id')
        comment = request.data.get('comment')  # Получаем комментарий

        if not photographer_id:
            return Response({'error': 'Не указан фотограф'}, status=400)
        
        # Проверяем, существует ли фотограф
        photographer = User.objects.filter(id=photographer_id).first()
        if not photographer:
            return Response({'error': 'Фотограф не найден'}, status=404)

        # Назначаем фотографа для заявки, сохраняем комментарий и обновляем статус
        st_request.photographer = photographer
        st_request.s_ph_comment = comment  # Сохраняем комментарий
        st_request.status_id = 3  # Обновляем статус заявки
        st_request.photo_date = timezone.now()  # Устанавливаем текущую дату и время в photo_date
        st_request.save()

        # Логируем операцию в таблицу ProductOperation
        # Допустим, у нас есть операция с типом 5 для назначения фотографа
        for st_request_product in st_request.strequestproduct_set.all():
            ProductOperation.objects.create(
                product=st_request_product.product,
                operation_type_id=5,  # ID типа операции для назначения фотографа
                user=photographer
            )
        
        return Response({'message': 'Фотограф успешно назначен и комментарий сохранен'}, status=200)
    
    except STRequest.DoesNotExist:
        return Response({'error': 'Заявка не найдена'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_retouchers(request):
    try:
        retouchers = User.objects.filter(groups__name='Ретушер', is_active=True)
        serializer = UserSerializer(retouchers, many=True)
        return Response(serializer.data, status=200)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_retoucher(request, request_number):
    try:
        retoucher_id = request.data.get('retoucher_id')
        comment = request.data.get('sr_comment')  # Получаем комментарий из запроса

        if not retoucher_id:
            return Response({'error': 'Не указан ретушер'}, status=400)

        st_request = STRequest.objects.get(RequestNumber=request_number)
        retoucher = User.objects.filter(id=retoucher_id).first()

        if not retoucher:
            return Response({'error': 'Ретушер не найден'}, status=404)

        # Назначаем ретушера и обновляем статус
        st_request.retoucher = retoucher
        st_request.status_id = 6  # Устанавливаем статус на "Ретушь"
        st_request.retouch_date = timezone.now()  # Устанавливаем текущую дату и время в retouch_date

        # Записываем комментарий, если он был передан
        if comment:
            st_request.sr_comment = comment

        st_request.save()

        return Response({'message': 'Ретушер успешно назначен'}, status=200)
    except STRequest.DoesNotExist:
        return Response({'error': 'Заявка не найдена'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_retouch_statuses_and_links(request, request_number):
    try:
        strequest = STRequest.objects.get(RequestNumber=request_number)

        # Получаем список баркодов с данными о статусе ретуши и ссылке
        barcodes = request.data.get('barcodes', [])

        for barcode_data in barcodes:
            barcode_value = barcode_data.get('barcode')
            retouch_status_id = barcode_data.get('retouch_status')
            retouch_link = barcode_data.get('retouch_link')

            # Находим продукт по штрихкоду в рамках текущей заявки
            try:
                strequest_product = STRequestProduct.objects.get(
                    request=strequest, product__barcode=barcode_value
                )
                
                # Обновляем статус ретуши и ссылку
                strequest_product.retouch_status_id = retouch_status_id
                strequest_product.product.retouch_link = retouch_link
                strequest_product.product.save()  # Сохраняем изменения продукта
                strequest_product.save()  # Сохраняем изменения для связи

            except STRequestProduct.DoesNotExist:
                continue  # Пропускаем, если продукт с баркодом не найден

        # Переводим заявку в статус 7 (Готово к проверке)
        strequest.status_id = 7
        strequest.save()

        return Response({'message': 'Статусы ретуши, ссылки и статус заявки обновлены'}, status=200)
    except STRequest.DoesNotExist:
        return Response({'error': 'Заявка не найдена'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def get_request_statuses(request):
    try:
        print("Fetching request statuses...")
        statuses = STRequestStatus.objects.all()
        print(f"Statuses retrieved: {[str(status) for status in statuses]}")  # Проверяем данные в статусах
        serializer = STRequestStatusSerializer(statuses, many=True)
        print(f"Serialized data: {serializer.data}")  # Проверяем сериализованные данные
        return Response(serializer.data)
    except Exception as e:
        print(f"Error fetching request statuses: {e}")
        return Response({"error": "Failed to fetch request statuses"}, status=500)

@api_view(['GET'])
def search_orders_by_barcode(request):
    barcode = request.query_params.get('barcode', None)
    if not barcode:
        return Response({"error": "Barcode is required"}, status=400)

    # Find orders containing the specified barcode
    orders = Order.objects.filter(orderproduct__product__barcode__icontains=barcode).distinct()
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)

class OrderStatusListView(APIView):
    def get(self, request):
        statuses = OrderStatus.objects.all()
        serializer = OrderStatusSerializer(statuses, many=True)
        return Response(serializer.data)

@api_view(['GET'])
def get_order_statuses(request):
    statuses = OrderStatus.objects.all()
    serializer = OrderStatusSerializer(statuses, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def order_details(request, orderNumber):
    try:
        # Retrieve order by order number
        order = Order.objects.get(OrderNumber=orderNumber)
        
        # Get products associated with the order
        order_products = OrderProduct.objects.filter(order=order).select_related('product')
        products_data = [
            {
                'barcode': order_product.product.barcode,
                'name': order_product.product.name,
                'movementStatus': order_product.product.move_status.name if order_product.product.move_status else 'Не указан',
                'cell': order_product.product.cell if order_product.product.cell else 'Не указана',
                'assembled': order_product.assembled,
                'assembled_date': order_product.assembled_date,
                'accepted': order_product.accepted,
                'accepted_date': order_product.accepted_date
            }
            for order_product in order_products
        ]
        
        # Formulate response data with order details, including the assembly user
        response_data = {
            'orderNumber': order.OrderNumber,
            'status': {
                'id': order.status.id,
                'name': order.status.name
            },
            'products': products_data,
            'creator': {
                'first_name': order.creator.first_name,
                'last_name': order.creator.last_name
            } if order.creator else None,
            'assembly_user': {
                'first_name': order.assembly_user.first_name,
                'last_name': order.assembly_user.last_name
            } if order.assembly_user else None  # Check if assembly_user exists
        }
        
        return Response(response_data)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)
    
@api_view(['PATCH'])
def update_order_status(request, orderNumber):
    try:
        # Получаем заказ по номеру
        order = Order.objects.get(OrderNumber=orderNumber)
        
        # Получаем новый статус из данных запроса
        new_status_id = request.data.get('status_id')
        if new_status_id is not None:
            order.status_id = new_status_id
            order.save()
            return Response({'message': 'Статус заказа обновлен'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'status_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def get_invoice_details(request, invoice_number):
    try:
        # Получаем накладную по номеру
        invoice = Invoice.objects.get(InvoiceNumber=invoice_number)
        
        # Получаем связанные продукты накладной с предварительной загрузкой заявок
        products = InvoiceProduct.objects.filter(invoice=invoice).prefetch_related(
            'product__strequestproduct_set__request'
        )

        # Формируем данные о продуктах
        products_data = []
        for product in products:
            # Получаем последнюю заявку для продукта
            request_product = product.product.strequestproduct_set.order_by('-id').first()
            request_number = request_product.request.RequestNumber if request_product and request_product.request else "N/A"

            products_data.append({
                'barcode': product.product.barcode,
                'name': product.product.name,
                'request_number': request_number,  # Добавляем номер заявки
                'quantity': 1,
                'cell': product.product.cell
            })
        
        # Формируем данные накладной
        invoice_data = {
            'InvoiceNumber': invoice.InvoiceNumber,
            'date': invoice.date,
            'creator': f"{invoice.creator.first_name} {invoice.creator.last_name}" if invoice.creator else "Не указан",
            'products': products_data
        }

        return Response(invoice_data, status=status.HTTP_200_OK)
    except Invoice.DoesNotExist:
        return Response({'error': 'Накладная не найдена'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def check_barcodes(request):
    barcodes = request.data.get('barcodes', [])
    missing_barcodes = []  # Здесь логика для проверки наличия штрихкодов в базе

    # Пример: добавьте штрихкоды в missing_barcodes, которые отсутствуют в базе
    for barcode in barcodes:
        if not Product.objects.filter(barcode=barcode).exists():
            missing_barcodes.append(barcode)
    
    return Response({'missing_barcodes': missing_barcodes}, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    try:
        # Собираем список всех shop_id из Blocked_Shops
        blocked_shop_ids = Blocked_Shops.objects.values_list('shop_id', flat=True)

        # Собираем список всех заблокированных баркодов
        blocked_barcodes = Blocked_Barcode.objects.values_list('barcode', flat=True)

        # Получаем штрихкоды из запроса
        barcodes = request.data.get('barcodes', [])
        missing_barcodes = []
        valid_products = []

        for barcode in barcodes:
            product = Product.objects.filter(barcode=barcode).first()
            if product:
                # Пропускаем товар, если seller есть в списке заблокированных магазинов
                if product.seller is not None and product.seller in blocked_shop_ids:
                    continue

                # Пропускаем товар, если сам штрихкод заблокирован
                if barcode in blocked_barcodes:
                    continue

                valid_products.append(product)
            else:
                missing_barcodes.append(barcode)

        # Если есть отсутствующие штрихкоды, возвращаем ошибку
        if missing_barcodes:
            return Response({
                'error': 'Некоторые штрихкоды не найдены в базе данных.',
                'missing_barcodes': missing_barcodes
            }, status=status.HTTP_400_BAD_REQUEST)

        # Получаем флаг приоритета из запроса
        priority_flag = request.data.get('priority', False)

        # Генерация нового номера заказа
        last_order = Order.objects.aggregate(Max('OrderNumber'))
        new_order_number = int(last_order['OrderNumber__max'] or 0) + 1
        while Order.objects.filter(OrderNumber=new_order_number).exists():
            new_order_number += 1

        current_date = timezone.now()
        creator_id = request.user.id

        # Создаём новый заказ
        order = Order.objects.create(
            OrderNumber=new_order_number,
            date=current_date,
            creator_id=creator_id,
            status_id=2  # Например, статус "Новый"
        )

        # Для каждого валидного продукта обновляем статус и, если требуется, приоритет
        for product in valid_products:
            if str(priority_flag).lower() == 'true':
                product.priority = True
            # Обновляем move_status на значение 2
            product.move_status_id = 2
            product.save()

            # Создаём запись в ProductOperation
            ProductOperation.objects.create(
                product=product,
                operation_type_id=2,
                user=request.user,
                comment=''  # Комментарий оставляем пустым
            )

            # Создаём запись в OrderProduct для связывания товара с заказом
            OrderProduct.objects.create(order=order, product=product)

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Exception as e:
        print(f"Error creating order: {e}")
        return Response({'error': 'Ошибка при создании заказа'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_products_batch(request):
    # Получаем данные из тела запроса
    data = request.data.get('data', [])
    
    # Проверка на отсутствие данных
    if not data:
        return Response({'error': 'Отсутствуют данные для загрузки'}, status=400)

    missing_data_rows = []  # Список для хранения строк с отсутствующими данными

    # Начинаем транзакцию для обработки данных
    with transaction.atomic():
        for index, row in enumerate(data):
            barcode = row.get('barcode')
            name = row.get('name')
            category_id = row.get('category_id')
            seller = row.get('seller')
            in_stock_sum = row.get('in_stock_sum')
            cell = row.get('cell')

            # Проверка на обязательные поля
            if not barcode or not name or category_id is None or seller is None or in_stock_sum is None:
                missing_data_rows.append({
                    'row': index + 1,
                    'barcode': barcode,
                    'name': name,
                    'category_id': category_id,
                    'seller': seller,
                    'in_stock_sum': in_stock_sum,
                    'cell': cell
                })
                continue  # Переходим к следующей записи

            try:
                # Создание или обновление записи
                Product.objects.update_or_create(
                    barcode=barcode,
                    defaults={
                        'name': name,
                        'category_id': category_id,
                        'seller': seller,
                        'in_stock_sum': in_stock_sum,
                        'cell': cell
                    }
                )
            except Exception as e:
                transaction.set_rollback(True)
                return Response({'error': f'Ошибка при загрузке данных: {str(e)}'}, status=400)

    # Проверка на наличие строк с отсутствующими обязательными данными
    if missing_data_rows:
        return Response({
            'error': 'Отсутствуют обязательные данные в строках.',
            'missing_data': missing_data_rows
        }, status=400)
    
    # Возвращаем успешный ответ, если все данные загружены корректно
    return Response({'message': 'Данные успешно загружены'}, status=201)

@api_view(['GET'])
def get_history_by_barcode(request, barcode):
    try:
        # История операций с продуктом
        history = ProductOperation.objects.filter(product__barcode=barcode).select_related('operation_type', 'user')

        # Получаем параметры сортировки
        sort_field = request.query_params.get('sort_field', 'date')
        sort_order = request.query_params.get('sort_order', 'desc')

        # Проверка сортировки по связанному полю
        if sort_field == 'operation_type_name':
            sort_field = 'operation_type__name'
        elif sort_field == 'user_full_name':
            sort_field = 'user__first_name'  # Сортировка по имени пользователя для упрощения

        if sort_order == 'desc':
            sort_field = f'-{sort_field}'

        # Применяем сортировку
        history = history.order_by(sort_field)

        # Пагинация
        paginator = ProductHistoryPagination()
        paginated_history = paginator.paginate_queryset(history, request)

        # Подготовка данных истории операций
        history_data = [
            {
                "operation_type_name": entry.operation_type.name,
                "user_full_name": f"{entry.user.first_name} {entry.user.last_name}" if entry.user else "Unknown",
                "date": entry.date,
                "comment": entry.comment
            }
            for entry in paginated_history
        ]

        # Получение последней заявки, связанной с продуктом
        last_request = (
            STRequestProduct.objects.filter(product__barcode=barcode)
            .select_related('request')
            .order_by('-request__creation_date')
            .first()
        )

        # Получение последней накладной, связанной с продуктом
        last_invoice = (
            InvoiceProduct.objects.filter(product__barcode=barcode)
            .select_related('invoice')
            .order_by('-invoice__date')
            .first()
        )

        # Сериализация последних заявки и накладной, если они существуют
        last_request_data = STRequestSerializer(last_request.request).data if last_request else None
        last_invoice_data = InvoiceSerializer(last_invoice.invoice).data if last_invoice else None

        # Ответ с историей операций и последней заявкой/накладной
        response_data = {
            "history": history_data,
            "last_request": last_request_data,
            "last_invoice": last_invoice_data
        }

        return paginator.get_paginated_response(response_data)

    except FieldError as e:
        return Response({'error': str(e)}, status=400)
    except ProductOperation.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)


# View for Move Statuses
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def move_statuses(request):
    try:
        statuses = ProductMoveStatus.objects.all()
        serializer = StatusSerializer(statuses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# View for Stockmen Users
@api_view(['GET'])
def stockman_list(request):
    stockman_group = Group.objects.filter(name="Товаровед").first()
    if not stockman_group:
        return Response({"error": "Group 'Товаровед' not found"}, status=404)

    stockmen = User.objects.filter(groups=stockman_group)
    stockmen_data = [{"id": stockman.id, "name": f"{stockman.first_name} {stockman.last_name}"} for stockman in stockmen]

    return Response(stockmen_data)

class ProductCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [IsAuthenticated]

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_categories(request):
    categories_data = request.data.get('categories', [])
    
    if not categories_data:
        return Response({'error': 'Нет данных для загрузки'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Обработка каждой категории
        for category_data in categories_data:
            category_id = category_data.get('id')
            name = category_data.get('name')
            reference_link = category_data.get('reference_link')

            # Создание или обновление категории
            ProductCategory.objects.update_or_create(
                id=category_id,
                defaults={
                    'name': name,
                    'reference_link': reference_link,
                }
            )

        return Response({'message': 'Категории успешно загружены'}, status=status.HTTP_201_CREATED)
    except IntegrityError as e:
        return Response({'error': f'Ошибка сохранения категории: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class CategoryListView(generics.ListAPIView):
    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CategoryPagination

    def get_queryset(self):
        queryset = ProductCategory.objects.all()
        
        # Filtering
        name = self.request.query_params.get('name', None)
        reference_link = self.request.query_params.get('reference_link', None)
        
        if name:
            queryset = queryset.filter(name__icontains=name)
        if reference_link:
            queryset = queryset.filter(reference_link__icontains=reference_link)

        # Sorting
        ordering = self.request.query_params.get('ordering', 'id')  # Default to sorting by ID
        if ordering:
            # Allows descending ordering with '-' prefix
            queryset = queryset.order_by(ordering)
        
        return queryset

class ProductCategoryFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr='icontains')  # Case-insensitive contains
    reference_link = filters.CharFilter(lookup_expr='icontains')  # Similar filter for links

    # Specify ordering filter
    ordering = filters.OrderingFilter(
        fields=(
            ('id', 'id'),
            ('name', 'name'),
            ('reference_link', 'reference_link'),
        )
    )

    class Meta:
        model = ProductCategory
        fields = ['name', 'reference_link']  # Fields that can be filtered


@api_view(['GET'])
def categories_list(request):
    categories = ProductCategory.objects.all()

    # Filtering
    category_id = request.query_params.get('id', None)
    name = request.query_params.get('name', None)
    reference_link = request.query_params.get('reference_link', None)

    if category_id:
        categories = categories.filter(id=category_id)
    if name:
        categories = categories.filter(name__icontains=name)
    if reference_link:
        categories = categories.filter(reference_link__icontains=reference_link)

    # Sorting
    sort_field = request.query_params.get('sort_field', 'id')
    sort_order = request.query_params.get('sort_order', 'asc')

    if sort_field:
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        categories = categories.order_by(sort_field)

    # Pagination
    paginator = ProductPagination()
    paginated_categories = paginator.paginate_queryset(categories, request)

    # Serialization
    serializer = ProductCategorySerializer(paginated_categories, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
def defect_operations_list(request):
    defect_operations = ProductOperation.objects.filter(operation_type_id__in=[25, 30])

    barcode = request.query_params.get('barcode', None)
    product_name = request.query_params.get('name', None)
    start_date = request.query_params.get('start_date', None)
    end_date = request.query_params.get('end_date', None)
    sort_field = request.query_params.get('sort_field', 'date')
    sort_order = request.query_params.get('sort_order', 'desc')

    # Массовый поиск по штрихкодам
    if barcode:
        if ',' in barcode:
            barcodes_list = [b.strip() for b in barcode.split(',') if b.strip()]
            defect_operations = defect_operations.filter(product__barcode__in=barcodes_list)
        else:
            defect_operations = defect_operations.filter(product__barcode__icontains=barcode)

    if product_name:
        defect_operations = defect_operations.filter(product__name__icontains=product_name)

    # Фильтрация по датам (включая границы)
    date_format = '%Y-%m-%d'
    try:
        if start_date:
            start_date_obj = datetime.strptime(start_date, date_format)
            defect_operations = defect_operations.filter(date__gte=start_date_obj)
        if end_date:
            end_date_obj = datetime.strptime(end_date, date_format)
            defect_operations = defect_operations.filter(date__lte=end_date_obj)
    except ValueError:
        return Response({"error": "Invalid date format, expected YYYY-MM-DD"}, status=400)

    defect_operations = defect_operations.annotate(
        user_full_name=Concat('user__first_name', Value(' '), 'user__last_name')
    )

    allowed_sort_fields = ['date', 'product__barcode', 'product__name', 'user_full_name']
    if sort_field not in allowed_sort_fields:
        return Response({"error": f"Invalid sort field: {sort_field}"}, status=400)

    if sort_order == 'desc':
        sort_field = f'-{sort_field}'

    defect_operations = defect_operations.order_by(sort_field)

    paginator = ProductHistoryPagination()
    paginated_operations = paginator.paginate_queryset(defect_operations, request)
    if paginated_operations is None:
        raise NotFound(detail="Invalid page.")

    serializer = DefectSerializer(paginated_operations, many=True)
    return paginator.get_paginated_response(serializer.data)

class PhotographerStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        selected_date = request.query_params.get('date')
        
        if not selected_date:
            return Response({"error": "Date parameter is required"}, status=400)

        # Преобразуем дату в формат datetime, если требуется
        try:
            selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        # Получаем список фотографов и вычисляем статистику
        stats = (
            User.objects
            .filter(groups__name="Фотограф")
            .annotate(
                # Подсчет уникальных заявок
                requests_count=Count(
                    'photographer_requests',
                    filter=Q(
                        photographer_requests__status_id__in=[5, 6, 7, 8, 9], 
                        photographer_requests__photo_date__date=selected_date
                    ),
                    distinct=True
                ),
                # Подсчет товаров, связанных с этими заявками
                total_products=Count(
                    'photographer_requests__strequestproduct',
                    filter=Q(
                        photographer_requests__status_id__in=[5, 6, 7, 8, 9], 
                        photographer_requests__photo_date__date=selected_date
                    )
                )
            )
            .values('id', 'first_name', 'last_name', 'requests_count', 'total_products')
        )

        return Response(stats)

class RetoucherStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        selected_date = request.query_params.get('date')
        
        if not selected_date:
            return Response({"error": "Date parameter is required"}, status=400)

        # Get retouchers and calculate stats
        stats = (
            User.objects
            .filter(groups__name="Ретушер")
            .annotate(
                # Count distinct requests
                requests_count=Count(
                    'retoucher_requests',
                    filter=Q(retoucher_requests__status_id__in=[8, 9], retoucher_requests__retouch_date__date=selected_date),
                    distinct=True
                ),
                # Count distinct products in the requests
                total_products=Count(
                    'retoucher_requests__strequestproduct__id',
                    filter=Q(retoucher_requests__status_id__in=[8, 9], retoucher_requests__retouch_date__date=selected_date),
                    distinct=True
                )
            )
            .values('id', 'first_name', 'last_name', 'requests_count', 'total_products')
        )

        return Response(stats)

class ManagerProductStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        selected_date = request.query_params.get('date')

        if not selected_date:
            return Response({"error": "Date parameter is required"}, status=400)

        # Total ordered items count for the selected date
        ordered_count = Order.objects.filter(date__date=selected_date).aggregate(ordered=Count('orderproduct'))

        # Aggregate accepted, shipped, and defective operations by user
        accepted = ProductOperation.objects.filter(
            operation_type=3,  # Accepted
            date__date=selected_date
        ).values('user_id').annotate(total=Count('id'))

        shipped = ProductOperation.objects.filter(
            operation_type=4,  # Shipped
            date__date=selected_date
        ).values('user_id').annotate(total=Count('id'))

        defective_count = ProductOperation.objects.filter(
            operation_type=25,  # Defective
            date__date=selected_date
        ).count()

        # Accepted products without requests for the selected date
        accepted_without_request = ProductOperation.objects.filter(
            operation_type=3,  # Accepted
            date__date=selected_date
        ).exclude(product__strequestproduct__isnull=False).count()

        # Construct response data
        stats = {
            "ordered": ordered_count['ordered'],
            "accepted": list(accepted),
            "shipped": list(shipped),
            "defective": defective_count,
            "accepted_without_request": accepted_without_request
        }

        return Response(stats)


class StockmanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stockman_group = Group.objects.get(name="Товаровед")
        stockmen = stockman_group.user_set.all().values('id', 'first_name', 'last_name')
        
        return Response(stockmen)

class ReadyPhotosView(APIView):
    permission_classes = []  # Public access
    pagination_class = ProductPagination  # Use pagination here

    def get(self, request):
        barcode = request.query_params.get('barcode', None)
        date_from = request.query_params.get('date_from', None)
        date_to = request.query_params.get('date_to', None)
        seller_id = request.query_params.get('seller_id', None)
        sort_field = request.query_params.get('sort_field', 'product__barcode')  # Default sort by product barcode
        sort_order = request.query_params.get('sort_order', 'asc')

        # Начинаем с фильтрации записей STRequestProduct по указанным условиям статуса
        ready_products = STRequestProduct.objects.filter(
            Q(request__status_id__in=[8, 9]) & Q(retouch_status_id=2)
        ).select_related('product', 'request')

        # Фильтрация по штрихкодам (поддержка нескольких значений)
        if barcode:
            barcode_list = [b.strip() for b in barcode.split(',') if b.strip()]
            ready_products = ready_products.filter(product__barcode__in=barcode_list)

        # Фильтрация по seller_id (поддержка нескольких значений)
        if seller_id:
            seller_list = [s.strip() for s in seller_id.split(',') if s.strip()]
            ready_products = ready_products.filter(product__seller__in=seller_list)

        # Фильтрация по диапазону дат (retouch_date из модели request)
        if date_from and date_to:
            try:
                from_date_obj = datetime.strptime(date_from, "%Y-%m-%d")
                to_date_obj = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
                ready_products = ready_products.filter(
                    request__retouch_date__gte=from_date_obj,
                    request__retouch_date__lt=to_date_obj
                )
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD for date_from and date_to."}, status=400)
        # Фильтрация по конкретной дате, если передан параметр date
        elif request.query_params.get('date', None):
            date = request.query_params.get('date')
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                ready_products = ready_products.filter(request__retouch_date__date=date_obj)
            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # Корректная сортировка по связанным полям
        if sort_field in ['barcode', 'name', 'seller_id']:
            sort_field = f'product__{sort_field}'
        if sort_order == 'desc':
            sort_field = f'-{sort_field}'
        ready_products = ready_products.order_by(sort_field)

        # Пагинация результатов
        paginator = ProductPagination()
        paginated_ready_products = paginator.paginate_queryset(ready_products, request)

        # Сериализация данных
        data = [
            {
                "barcode": rp.product.barcode,
                "name": rp.product.name,
                "seller_id": rp.product.seller,
                "retouch_link": rp.product.retouch_link
            }
            for rp in paginated_ready_products if rp.product.retouch_link
        ]

        return paginator.get_paginated_response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_assembly(request, order_number):
    print(f"Order Number received: {order_number}")
    user_id = request.data.get('user_id')
    user = get_object_or_404(User, id=user_id)
    order = get_object_or_404(Order, OrderNumber=order_number)

    order.assembly_user = user
    order.assembly_date = timezone.now()
    order.status_id = 3  # Set status to 3 for assembly started
    order.save()

    return Response({'message': 'Assembly started and user assigned'}, status=200)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assemble_product(request, order_number, product_barcode):
    order = get_object_or_404(Order, OrderNumber=order_number)
    try:
        order_product = OrderProduct.objects.get(order=order, product__barcode=product_barcode)
        order_product.assembled = True
        order_product.assembled_date = timezone.now()
        order_product.save()
        return Response({'message': 'Товар успешно добавлен'}, status=200)
    except OrderProduct.DoesNotExist:
        return Response({'error': 'Этого ШК нет в данном заказе'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_acceptance(request, order_number):
    user_id = request.data.get('user_id')
    user = get_object_or_404(User, id=user_id)
    order = get_object_or_404(Order, OrderNumber=order_number)

    order.accept_user = user
    order.accept_date = timezone.now()
    order.status_id = 4  # Set status to 4 for acceptance started
    order.save()

    return Response({'message': 'Acceptance started and user assigned'}, status=200)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_order_products(request, order_number):
    barcodes = request.data.get('barcodes', [])
    order = get_object_or_404(Order, OrderNumber=order_number)
    not_found_barcodes = []

    for barcode in barcodes:
        try:
            order_product = OrderProduct.objects.get(order=order, product__barcode=barcode)
            order_product.accepted = True
            order_product.accepted_date = timezone.now()
            order_product.save()
        except OrderProduct.DoesNotExist:
            not_found_barcodes.append(barcode)

    if not_found_barcodes:
        return Response({
            'message': 'Часть товаров приняты, непринятые:',
            'missing_barcodes': not_found_barcodes
        }, status=207)

    return Response({'message': 'Все товары успешно приняты'}, status=200)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_order_status(request, order_number, new_status):
    order = get_object_or_404(Order, OrderNumber=order_number)
    order.status_id = new_status
    order.save()
    return Response({'message': f'Статус заказа обновлен на {new_status}'}, status=200)

@api_view(['GET'])
def check_order_status(request, order_number):
    try:
        order = Order.objects.get(OrderNumber=order_number)
        order_products = OrderProduct.objects.filter(order=order)

        # Проверяем, совпадают ли assembled и accepted для каждого продукта
        all_match = all(product.assembled == product.accepted for product in order_products)

        # Если у всех продуктов `assembled` и `accepted` совпадают
        if all_match:
            order.status_id = 5  # Устанавливаем статус "5" если все продукты совпадают по `assembled` и `accepted`
        else:
            order.status_id = 6  # Устанавливаем статус "6" если есть хотя бы одно расхождение

        order.save()
        return Response({'message': f'Order status updated to {order.status_id}'}, status=200)
        
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_opened(request):
    barcode = request.data.get('barcode')
    user_id = request.data.get('userId')
    comment = "Вскрыто"  # Default comment for "Вскрыто" operation

    if not barcode or not user_id:
        return Response({'error': 'Barcode and userId are required'}, status=400)

    # Retrieve the user
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    # Retrieve the product and update its status
    try:
        product = Product.objects.get(barcode=barcode)
        product.move_status_id = 30  # Set status to "Вскрыто"
        product.save()
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)

    # Log the operation
    try:
        ProductOperation.objects.create(
            product=product,
            operation_type_id=30,  # Operation type "Вскрыто"
            user=user,
            comment=comment,
            date=timezone.now()
        )
    except Exception as e:
        return Response({'error': f'Failed to log operation: {str(e)}'}, status=500)

    return Response({'message': 'Product marked as opened, status updated, and logged successfully'}, status=200)

class UserURLsViewSet(ModelViewSet):
    queryset = UserURLs.objects.all()
    serializer_class = UserURLsSerializer

# ViewSet для STRequestHistory
class STRequestHistoryViewSet(ModelViewSet):
    queryset = STRequestHistory.objects.select_related('st_request', 'product', 'user', 'operation').all()
    serializer_class = STRequestHistorySerializer
    pagination_class = ProductHistoryPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    # Настройка фильтров
    filterset_fields = {
        'st_request__RequestNumber': ['exact'],  # Фильтр по номеру заявки
        'product__barcode': ['exact'],          # Фильтр по штрихкоду
        'user__id': ['exact'],                  # Фильтр по ID пользователя
        'operation__id': ['exact'],             # Фильтр по ID операции
        'date': ['gte', 'lte'],                 # Фильтр по дате (больше/меньше)
    }
    search_fields = [
        'st_request__RequestNumber',            # Поиск по номеру заявки
        'product__barcode',
        'product__name',                        # Поиск по наименованию продукта
        'user__first_name',                     # Поиск по имени пользователя
        'user__last_name',                      # Поиск по фамилии пользователя
        'user__username',                       # Поиск по username пользователя
        'operation__name'                       # Поиск по названию операции
    ]
    ordering_fields = ['date', 'st_request__RequestNumber', 'product__barcode', 'user__username', 'operation__name']
    ordering = ['-date']  # Сортировка по умолчанию

def accepted_products_by_category(request):
    qs = (
        Product.objects
        .filter(income_date__isnull=False)
        .values('category_id')
        .annotate(count=Count('id'))
        .order_by('-count')  # Сортировка по убыванию
    )
    data = list(qs)  # [{'category_id': 1, 'count': 42}, {'category_id': 2, 'count': 17}, ...]

    return render(request, 'core/accepted_products_by_category.html', {'data': data})

class NofotoListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = NofotoListSerializer
    pagination_class = NofotoPagination

    queryset = Nofoto.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product__barcode', 'product__name', 'product__seller', 'date']
    search_fields = ['product__barcode', 'product__name']
    ordering_fields = ['date', 'product__barcode', 'product__seller', 'product__name']
    ordering = ['-date']

    def get_queryset(self):
        qs = super().get_queryset()

        start_date_str = self.request.query_params.get('start_date')
        end_date_str   = self.request.query_params.get('end_date')

        # 1) Фильтр по дате "с ... "
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
                qs = qs.filter(date__gte=start_dt)
            except ValueError:
                pass  # Можно вернуть ошибку или проигнорировать

        # 2) Фильтр по дате "... по"
        #    Прибавляем +1 день и используем < (strictly less), чтобы включить
        #    записи за весь этот день по локальному времени.
        if end_date_str:
            try:
                end_dt = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
                qs = qs.filter(date__lt=end_dt)
            except ValueError:
                pass

        # 3) Фильтр по магазинам (через параметр ?seller=111,222)
        seller_str = self.request.query_params.get('seller')
        if seller_str:
            sellers = [s.strip() for s in seller_str.split(',') if s.strip()]
            qs = qs.filter(product__seller__in=sellers)

        # 4) Фильтр по штрихкодам (через параметр ?barcodes=111,222)
        barcodes_str = self.request.query_params.get('barcodes')
        if barcodes_str:
            splitted = [bc.strip() for bc in barcodes_str.split(',') if bc.strip()]
            qs = qs.filter(product__barcode__in=splitted)

        return qs

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_product_info(request):
    # Получаем данные из запроса
    barcodes = request.data.get('barcodes')
    info = request.data.get('info')

    # Проверяем корректность входных данных
    if not barcodes or not isinstance(barcodes, list):
        return Response(
            {"error": "Поле 'barcodes' должно быть непустым списком."},
            status=status.HTTP_400_BAD_REQUEST
        )
    if info is None:
        return Response(
            {"error": "Поле 'info' обязательно для заполнения."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Получаем продукты, существующие по заданным штрихкодам
    products = Product.objects.filter(barcode__in=barcodes)

    # Обновляем поле info для найденных товаров
    updated_count = products.update(info=info)

    # Определяем штрихкоды, которых нет в базе
    existing_barcodes = list(products.values_list('barcode', flat=True))
    missing_barcodes = [barcode for barcode in barcodes if barcode not in existing_barcodes]

    return Response(
        {
            "message": f"Информация обновлена для {updated_count} товаров.",
            "missing_barcodes": missing_barcodes
        },
        status=status.HTTP_200_OK
    )

@transaction.non_atomic_requests
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_blocked_barcodes(request):
    barcodes_raw = request.data.get('barcodes')
    if not barcodes_raw:
        return Response({"error": "Поле 'barcodes' обязательно."}, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(barcodes_raw, str):
        barcodes = [b.strip() for b in barcodes_raw.splitlines() if b.strip()]
    elif isinstance(barcodes_raw, list):
        barcodes = [str(b).strip() for b in barcodes_raw if str(b).strip()]
    else:
        return Response({"error": "Неверный формат данных."}, status=status.HTTP_400_BAD_REQUEST)

    if not barcodes:
        return Response({"error": "Нет валидных штрихкодов для добавления."}, status=status.HTTP_400_BAD_REQUEST)

    created = 0
    for barcode in barcodes:
        # Убираем try/except для диагностики
        obj, is_created = Blocked_Barcode.objects.get_or_create(barcode=barcode)
        if is_created:
            created += 1

    return Response({"message": f"Добавлено {created} штрихкодов."}, status=status.HTTP_201_CREATED)

def order_product_list(request):
    # Подзапрос для получения последней накладной для товара
    latest_invoice = InvoiceProduct.objects.filter(
        product=OuterRef('product')
    ).order_by('-invoice__date', '-invoice__id')
    
    # Аннотируем OrderProduct, добавляя поле last_invoice_number
    order_products = OrderProduct.objects.select_related(
        'order', 'product', 'product__move_status'
    ).annotate(
        last_invoice_number=Subquery(latest_invoice.values('invoice__InvoiceNumber')[:1])
    )
    
    return render(request, 'core/order_product_table.html', {'order_products': order_products})

#получению ключа гугла
class GetNextAPIKeyView(APIView):
    """
    Эндпоинт для циклической выдачи ключей Google API.
    Требует JWT аутентификации.
    Использует кэш для хранения списка ключей и индекса последнего выданного ключа.

    Константы для кэша определены как атрибуты этого класса.

    ВНИМАНИЕ: Отправка API ключей клиенту небезопасна!
    Этот эндпоинт предоставляется согласно запросу, но рекомендуется
    реализовать прокси на бэкенде, который сам будет использовать ключи.
    """
    permission_classes = [IsAuthenticated]

    # --- Константы определены внутри класса ---
    API_KEY_LIST_CACHE_KEY = 'google_api_keys_list_v3_scoped' # Уникальный ключ для списка ключей (в области видимости класса)
    LAST_API_KEY_INDEX_CACHE_KEY = 'last_google_api_key_index_scoped' # Уникальный ключ для индекса (в области видимости класса)
    CACHE_TIMEOUT_KEYS_LIST = 60 * 15 # Кэшировать список ключей на 15 минут

    def _get_cached_keys(self):
        """Вспомогательный метод для получения списка ключей из кэша или БД."""
        # Доступ к константам через self
        api_keys_list = cache.get(self.API_KEY_LIST_CACHE_KEY)
        if api_keys_list is None:
            logger.info("API keys not found in cache. Fetching from DB.")
            try:
                keys_queryset = APIKeys.objects.values_list('key', flat=True).order_by('id')
                api_keys_list = list(keys_queryset)
                if api_keys_list:
                    # Доступ к константам через self
                    cache.set(self.API_KEY_LIST_CACHE_KEY, api_keys_list, self.CACHE_TIMEOUT_KEYS_LIST)
                    logger.info(f"Cached {len(api_keys_list)} API keys.")
                else:
                     # Доступ к константам через self (хотя таймаут здесь можно задать явно)
                     cache.set(self.API_KEY_LIST_CACHE_KEY, [], 60 * 5)
                     logger.warning("No APIKeys found in the database.")
            except Exception as e:
                logger.error(f"Error fetching APIKeys from database: {e}", exc_info=True)
                return None
        return api_keys_list

    def get(self, request, *args, **kwargs):
        api_keys = self._get_cached_keys()

        if api_keys is None:
            return Response(
                {"error": "Server error: Could not retrieve API keys configuration."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if not api_keys:
            return Response(
                {"error": "Service unavailable: No API keys configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        num_keys = len(api_keys)

        # Доступ к константе через self
        last_index = cache.get(self.LAST_API_KEY_INDEX_CACHE_KEY, default=-1)

        try:
            last_index = int(last_index)
        except (ValueError, TypeError):
            logger.warning(f"Invalid index '{last_index}' found in cache, resetting.")
            last_index = -1

        next_index = (last_index + 1) % num_keys

        try:
            next_key = api_keys[next_index]
        except IndexError:
             logger.error(f"Calculated next_index {next_index} is out of bounds for {num_keys} keys.")
             next_index = 0
             if not api_keys:
                 return Response(
                    {"error": "Service unavailable: No API keys configured."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                 )
             next_key = api_keys[next_index]

        # Доступ к константе через self
        cache.set(self.LAST_API_KEY_INDEX_CACHE_KEY, next_index, timeout=None)

        logger.warning(
            f"Issuing Google API Key (Index {next_index}) directly to client "
            f"(User ID: {request.user.id}). This approach is insecure."
        )
        return Response({"api_key": next_key}, status=status.HTTP_200_OK)

class GetUserWorkStatusView(APIView):
    """
    API эндпоинт для получения текущего рабочего статуса (on_work)
    аутентифицированного пользователя.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            # Пытаемся получить профиль пользователя через related_name 'profile'
            user_profile = request.user.profile
            on_work_status = user_profile.on_work
        except UserProfile.DoesNotExist:
            # Если профиль не найден, можно вернуть ошибку или статус по умолчанию.
            # Возврат ошибки более явный.
            # В качестве альтернативы, если профиль может отсутствовать и это означает "не на работе":
            on_work_status = False 
            return Response(
                {"error": "Профиль пользователя не найден."},
                status=status.HTTP_404_NOT_FOUND
            )
        except AttributeError:
            # Это может произойти, если request.user - AnonymousUser, хотя IsAuthenticated должен это предотвратить.
            # Или если у объекта user по какой-то причине нет атрибута 'profile' (менее вероятно с OneToOne).
             return Response(
                {"error": "Не удалось получить доступ к профилю пользователя."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


        return Response({"on_work": on_work_status}, status=status.HTTP_200_OK)

# Эндпоинт для переключения статуса on_work пользователя
class ToggleUserWorkStatusView(APIView):
    """
    API эндпоинт для переключения рабочего статуса (on_work)
    аутентифицированного пользователя на противоположный.
    Возвращает новый установленный статус.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Получаем или создаем профиль пользователя.
        # get_or_create возвращает кортеж (object, created_boolean)
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)

        # Если профиль был только что создан, user_profile.on_work будет значением по умолчанию (False).
        # Инвертируем текущее значение on_work.
        user_profile.on_work = not user_profile.on_work
        
        # Сохраняем изменения. Поле updated_at обновится автоматически благодаря auto_now=True.
        user_profile.save(update_fields=['on_work'])

        return Response(
            {
                "message": "Рабочий статус успешно обновлен.",
                "on_work": user_profile.on_work
            },
            status=status.HTTP_200_OK
        )
