from datetime import date, timedelta, datetime
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import Group, User
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
from django_filters import rest_framework as django_filters
from django_q.tasks import async_task
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view, permission_classes
from rest_framework import generics, permissions, status, filters
from .pagination import StandardResultsSetPagination, SRReadyProductsPagination, RetouchRequestPagination, ReadyPhotosPagination
from .filters import SRReadyProductFilter, ProductOperationFilter
from core.models import (
    UserProfile,
    Product,
    ProductOperation,
    ProductMoveStatus,
    STRequest,
    STRequestStatus,
    STRequestProduct,
    STRequestHistory,
    STRequestHistoryOperations,
    Product,
    ProductOperation,
    ProductOperationTypes,
    PhotoStatus,
    SPhotoStatus,
    UserProfile,
    Camera,
    STRequestProduct,
    PhotoStatus,
    STRequestPhotoTime,
    RetouchRequest,
    RetouchRequestProduct,
    RetouchRequestStatus,
    RetouchStatus,
    SRetouchStatus,
    Nofoto
)
from .serializers import (
    UserProfileSerializer,
    ProductSerializer,
    STRequestSerializer,
    STRequestPhotographerListSerializer,
    PhotographerSTRequestSerializer,
    CameraSerializer,
    PhotographerProductSerializer,
    SPhotographerRequestListSerializer,
    SPhotographerRequestDetailSerializer,
    PhotoStatusSerializer,
    SPhotoStatusSerializer,
    PhotographerUserSerializer,
    SRReadyProductSerializer,
    SRRetouchRequestCreateSerializer,
    SRRetouchersSerializer,
    SRRetouchRequestSerializer,
    RetouchRequestListSerializer,
    RetouchRequestDetailSerializer,
    RetouchRequestAssignSerializer,
    RetouchStatusSerializer,
    SRetouchStatusSerializer,
    RetouchStatusUpdateSerializer,
    SRetouchStatusUpdateSerializer,
    RetouchRequestSetStatusSerializer,
    ReadyPhotosSerializer,
    StockmanIncomeSerializer,
    StockmanOutcomeSerializer,
    StockmanDefectSerializer,
    StockmanOpenedSerializer,
    STRequestCreateSerializer,
    NofotoCreateSerializer,
    ProductOperationSerializer,
    ProductOperationTypesSerializer
)

# CRUD для UserProfile
class UserProfileListCreateView(generics.ListCreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

class UserProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

# CRUD для Product
class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

# CRUD для STRequest
class STRequestListCreateView(generics.ListCreateAPIView):
    queryset = STRequest.objects.all()
    serializer_class = STRequestSerializer
    permission_classes = [IsAuthenticated]

class STRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = STRequest.objects.all()
    serializer_class = STRequestSerializer
    permission_classes = [IsAuthenticated]

def server_time(request):
    current_time = timezone.now().isoformat()
    return JsonResponse({"server_time": current_time})

class UserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        try:
            # Доступ к профилю пользователя
            profile = request.user.profile  # Связанное поле OneToOneField
            on_work = profile.on_work
        except UserProfile.DoesNotExist:
            on_work = None

        # Получение групп пользователя
        groups = request.user.groups.values_list('name', flat=True)

        return Response({
            "id": request.user.id,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "on_work": on_work,
            "groups": list(groups),  # Добавляем список групп
        })

class UpdateOnWorkView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        print("Метод patch вызван")
        print(f"Пользователь: {request.user}")  # Проверка текущего пользователя
        print(f"Тело запроса: {request.data}")  # Проверка тела запроса

        try:
            profile = UserProfile.objects.get(user=request.user)
            print(f"Профиль найден: {profile}")
            
            on_work = request.data.get('on_work', None)
            if on_work is not None:
                profile.on_work = bool(on_work)
                profile.save()

                return Response({
                    "message": "Статус обновлен",
                    "on_work": profile.on_work
                }, status=status.HTTP_200_OK)

            return Response({
                "error": "Не передан статус"
            }, status=status.HTTP_400_BAD_REQUEST)

        except UserProfile.DoesNotExist:
            print("Профиль пользователя не найден")
            return Response({
                "error": "Пользователь не найден"
            }, status=status.HTTP_404_NOT_FOUND)

class PhotographerSTRequestListView(generics.ListAPIView):
    serializer_class = STRequestPhotographerListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Фильтруем заявки для текущего пользователя, у которых статус равен 3
        return STRequest.objects.filter(photographer=user, status_id=3)

class PhotographerSTRequestDetailView(APIView):
    """
    Возвращает детали одной заявки для фотографа.
    """
    def get(self, request, request_number):
        try:
            # Ищем заявку по номеру
            st_request = STRequest.objects.get(RequestNumber=request_number)

            # Сериализуем данные заявки
            serializer = PhotographerSTRequestSerializer(st_request)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except STRequest.DoesNotExist:
            return Response({"error": "Заявка не найдена"}, status=status.HTTP_404_NOT_FOUND)

class CameraListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cameras = Camera.objects.all()
        serializer = CameraSerializer(cameras, many=True)
        return Response(serializer.data)

class PhotographerProductView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, barcode):
        try:
            # Получаем продукт по штрихкоду
            product = Product.objects.get(barcode=barcode)

            # Получаем номер заявки из параметров запроса
            request_number = request.query_params.get("request_number")
            if not request_number:
                return Response(
                    {"error": "Не указан номер заявки"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Сериализуем данные, передавая context с request_number
            serializer = PhotographerProductSerializer(product, context={"request_number": request_number})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Product.DoesNotExist:
            # Если продукт не найден
            return Response(
                {"error": "Продукт с таким штрихкодом не найден"},
                status=status.HTTP_404_NOT_FOUND,
            )

class PhotographerUpdateProductView(APIView):
    def post(self, request):
        request_number = request.data.get('STRequestNumber')
        barcode = request.data.get('barcode')
        photo_status_id = request.data.get('photo_status')
        photos_link = request.data.get('photos_link')

        # Проверяем, что необходимые поля переданы
        if not request_number or not barcode:
            return Response({"error": "STRequestNumber и barcode являются обязательными полями."}, 
                            status=status.HTTP_400_BAD_REQUEST)

        # Находим заявку
        try:
            st_request = STRequest.objects.get(RequestNumber=request_number)
        except STRequest.DoesNotExist:
            return Response({"error": "Заявка с таким номером не найдена."}, 
                            status=status.HTTP_404_NOT_FOUND)

        # Находим продукт
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return Response({"error": "Продукт с таким штрихкодом не найден."}, 
                            status=status.HTTP_404_NOT_FOUND)

        # Находим связку STRequestProduct
        try:
            st_request_product = STRequestProduct.objects.get(request=st_request, product=product)
        except STRequestProduct.DoesNotExist:
            return Response({"error": "Связка STRequestProduct не найдена."}, 
                            status=status.HTTP_404_NOT_FOUND)

        # Проверяем, указан ли photo_status, и валиден ли он
        if photo_status_id is not None:
            try:
                photo_status = PhotoStatus.objects.get(id=photo_status_id)
            except PhotoStatus.DoesNotExist:
                return Response({"error": "Указанный photo_status не найден."}, 
                                status=status.HTTP_404_NOT_FOUND)
            st_request_product.photo_status = photo_status

        # Обновляем photos_link, если оно передано
        if photos_link is not None:
            st_request_product.photos_link = photos_link

        # Сохраняем изменения
        st_request_product.save()

        return Response({"message": "STRequestProduct успешно обновлён."}, status=status.HTTP_200_OK)


class CreateSTRequestPhotoTimeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request_number = request.data.get('request_number')
        barcode = request.data.get('barcode')

        # Проверим, что оба параметра есть в запросе
        if not request_number or not barcode:
            return Response({'error': 'request_number and barcode are required'}, status=400)

        # Находим соответствующие объекты
        st_request = get_object_or_404(STRequest, RequestNumber=request_number)
        product = get_object_or_404(Product, barcode=barcode)
        st_request_product = get_object_or_404(STRequestProduct, request=st_request, product=product)

        # Создаем запись в STRequestPhotoTime
        st_request_photo_time = STRequestPhotoTime.objects.create(
            st_request_product=st_request_product,
            user=request.user,
            photo_date=timezone.now()
        )

        # --- Added functionality: Create ProductOperation entry ---
        try:
            # Get the operation type (assuming id=50 exists)
            operation_type_instance = get_object_or_404(ProductOperationTypes, id=50)

            # Create the ProductOperation record
            ProductOperation.objects.create(
                product=product,
                operation_type=operation_type_instance,
                user=request.user,
                comment=str(request_number) # Ensure request_number is a string for the TextField
            )
        except ProductOperationTypes.DoesNotExist:
            # Handle the case where operation_type with id=50 does not exist
            # You might want to log this error or return a specific response
            return Response({'error': 'ProductOperationType with id 50 not found. Cannot log product operation.'}, status=500)
        except Exception as e:
            # Handle other potential errors during ProductOperation creation
            # Log the error e
            return Response({'error': f'Failed to create ProductOperation: {str(e)}'}, status=500)
        # --- End of added functionality ---

        # Формируем ответ. Если поле info не пустое, добавляем его в тело ответа.
        response_data = {
            'message': 'Photo time created successfully',
            'id': st_request_photo_time.id,
        }
        if product.info:
            response_data['info'] = product.info

        return Response(response_data, status=201)

class GetPhotoTimesByRequestNumberView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        request_number = request.query_params.get('request_number')

        if not request_number:
            return Response({'error': 'request_number is required'}, status=400)

        st_request = get_object_or_404(STRequest, RequestNumber=request_number)

        # Получаем только те записи, у которых user = request.user
        photo_times = STRequestPhotoTime.objects.filter(
            st_request_product__request=st_request,
            user=request.user
        )

        result = []
        for pt in photo_times:
            barcode = pt.st_request_product.product.barcode
            photo_date = pt.photo_date.isoformat() if pt.photo_date else None
            result.append({
                'barcode': barcode,
                'photo_date': photo_date
            })

        return Response(result, status=200)

class StartShootingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request_number = request.data.get('request_number')
        barcode = request.data.get('barcode')

        if not request_number or not barcode:
            return Response({'error': 'request_number and barcode are required'}, status=400)

        st_request = get_object_or_404(STRequest, RequestNumber=request_number)
        product = get_object_or_404(Product, barcode=barcode)
        st_request_product = get_object_or_404(STRequestProduct, request=st_request, product=product)

        # Предполагается, что PhotoStatus с pk=10 уже есть в базе данных
        photo_status_obj = get_object_or_404(PhotoStatus, pk=10)

        st_request_product.photo_status = photo_status_obj
        st_request_product.save()

        return Response({'message': 'Photo status updated to 10'}, status=200)

class SPhotographerRequestsListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SPhotographerRequestListSerializer
    pagination_class = StandardResultsSetPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['RequestNumber', 'strequestproduct__product__barcode']
    ordering_fields = [
        'RequestNumber', 
        'creation_date', 
        'photographer__last_name', 
        'photographer__first_name', 
        'priority_count'  
    ]
    ordering = ['-priority_count', 'creation_date']

    def get_queryset(self):
        queryset = STRequest.objects.all().annotate(
            priority_count=Count(
                'strequestproduct',
                filter=Q(strequestproduct__product__priority=True)
            )
        )

        # Получаем параметр status_id__in из query params
        status_in_param = self.request.query_params.get('status_id__in', None)
        if status_in_param:
            # Преобразуем строку '3,4,5' в список [3,4,5]
            status_ids = [int(s) for s in status_in_param.split(',') if s.isdigit()]
            queryset = queryset.filter(status_id__in=status_ids)
        else:
            # Если параметр не передан, используем статичный фильтр
            queryset = queryset.filter(status_id__in=[3,4,5])

        return queryset

class PhotoStatusListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = PhotoStatus.objects.all()
        serializer = PhotoStatusSerializer(qs, many=True)
        return Response(serializer.data)


class SPhotoStatusListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = SPhotoStatus.objects.all()
        serializer = SPhotoStatusSerializer(qs, many=True)
        return Response(serializer.data)

class SPhotographerRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        request_number = request.query_params.get('request_number', None)
        if not request_number:
            return Response({"error": "request_number is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            st_request = STRequest.objects.get(RequestNumber=request_number)
        except STRequest.DoesNotExist:
            return Response({"error": "STRequest not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = SPhotographerRequestDetailSerializer(st_request)
        return Response(serializer.data)

class OnWorkPhotographersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            group = Group.objects.get(name="Фотограф")
        except Group.DoesNotExist:
            return Response([], status=status.HTTP_200_OK)
        users = User.objects.filter(groups=group, profile__on_work=True)
        serializer = PhotographerUserSerializer(users, many=True)
        return Response(serializer.data)

def upcoming_birthdays(request):
    # Сегодняшняя дата
    today = date.today()

    # Список дат на ближайшие 10 дней (включая сегодня)
    upcoming_dates = [(today + timedelta(days=i)) for i in range(10)]

    # Приведём список дат к формату (месяц, день) для удобства сравнения
    upcoming_md = [(d.month, d.day) for d in upcoming_dates]

    # Загружаем всех пользователей с датой рождения
    # Можно оптимизировать запрос: .select_related('user') для уменьшения количества запросов
    profiles = UserProfile.objects.select_related('user').filter(birth_date__isnull=False)

    # Фильтруем профили, у которых день рождения попадает в следующие 10 дней
    result = []
    for profile in profiles:
        bd = profile.birth_date
        if (bd.month, bd.day) in upcoming_md:
            # Форматируем дату рождения (без года)
            birth_str = bd.strftime('%d.%m')
            # Добавляем в результат словарь с именем, фамилией и датой
            result.append({
                'first_name': profile.user.first_name,
                'last_name': profile.user.last_name,
                'birth_date': birth_str
            })

    return JsonResponse(result, safe=False)

class SRReadyProductsListView(generics.ListAPIView):
    queryset = STRequestProduct.objects.filter(photo_status=1, sphoto_status=1)
    serializer_class = SRReadyProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = SRReadyProductFilter
    pagination_class = SRReadyProductsPagination

    # Добавляем поле status в доступные поля для сортировки.
    # Если статус - связанное поле, возможно понадобится 'request__status_id' или 'request__status__name'
    ordering_fields = ['product__barcode', 'product__name', 'request__photo_date', 'product__priority', 'OnRetouch', 'request__status_id']

    def get_queryset(self):
        qs = super().get_queryset()
        # Дефолтная сортировка, если нужна
        return qs.order_by('-product__priority', 'request__photo_date')

class SRRetouchRequestCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SRRetouchRequestCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rr = serializer.save()
        rr_serializer = SRRetouchRequestSerializer(rr)
        return Response(rr_serializer.data, status=status.HTTP_201_CREATED)

class SRetouchersListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SRRetouchersSerializer

    def get_queryset(self):
        # Находим группу "Retoucher"
        try:
            retoucher_group = Group.objects.get(name="Ретушер")
        except Group.DoesNotExist:
            return UserProfile.objects.none()

        # Фильтруем пользователей, которые:
        # - находятся в группе Retoucher
        # - user.profile.on_work = True
        return UserProfile.objects.filter(
            on_work=True,
            user__groups=retoucher_group
        ).select_related('user')

class SRRetouchRequestListView(generics.ListAPIView):
    """
    Список заявок на ретушь (старший ретушер).
    Если в URL есть status_id, фильтруем, иначе показываем все.
    Пример: /sr-request-list/2/ — только статус=2
            /sr-request-list/   — все статусы
    """
    serializer_class = RetouchRequestListSerializer
    pagination_class = RetouchRequestPagination
    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    # Если нужна фильтрация по полям запроса: filterset_fields = ['status', 'priority']
    ordering_fields = ['RequestNumber', 'creation_date', 'status', 'priority']
    ordering = ['-creation_date']  # Дефолтная сортировка

    def get_queryset(self):
        queryset = RetouchRequest.objects.select_related('retoucher', 'status')
        status_id = self.kwargs.get('status_id')  # ловим из URL
        if status_id:
            queryset = queryset.filter(status_id=status_id)
        return queryset


class SRRetouchRequestDetailView(generics.RetrieveAPIView):
    """
    Детальная заявка для старшего ретушера:
    /sr-request-detail/<int:request_number>/
    """
    serializer_class = RetouchRequestDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'RequestNumber'  # Поиск по полю RequestNumber

    def get_queryset(self):
        return RetouchRequest.objects.select_related('retoucher', 'status')

class SRetouchRequestListView(generics.ListAPIView):
    """
    Список заявок для обычного ретушера:
    Показываем только те заявки, где RetouchRequest.retoucher == request.user
    Если в URL указан status_id, фильтруем дополнительно.
    """
    serializer_class = RetouchRequestListSerializer
    pagination_class = RetouchRequestPagination
    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['RequestNumber', 'creation_date', 'status', 'priority']
    ordering = ['-creation_date']

    def get_queryset(self):
        queryset = RetouchRequest.objects.select_related('retoucher', 'status')\
                                         .filter(retoucher=self.request.user)

        status_id = self.kwargs.get('status_id')
        if status_id:
            queryset = queryset.filter(status_id=status_id)
        return queryset

class SRetouchRequestDetailView(generics.RetrieveAPIView):
    """
    Детальная заявка для обычного ретушера:
    Отдаём только если текущий пользователь = retoucher заявки.
    """
    serializer_class = RetouchRequestDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'RequestNumber'

    def get_queryset(self):
        return RetouchRequest.objects.select_related('retoucher', 'status')\
                                     .filter(retoucher=self.request.user)

class RetouchStatusListView(generics.ListAPIView):
    serializer_class = RetouchStatusSerializer
    
    def get_queryset(self):
        return RetouchStatus.objects.all()

class SRetouchStatusListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SRetouchStatusSerializer
    
    def get_queryset(self):
        return SRetouchStatus.objects.all()

class UpdateRetouchStatusView(APIView):
    """
    POST /ft/retoucher/update-retouch-status/
    body: {
      "request_number": 123,
      "barcode": "1234567890123",
      "retouch_status_id": 2,
      "retouch_link": "http://..."   # опционально
    }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = RetouchStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rrp = serializer.save()  # retouch_request_product
        return Response({
            "detail": "Retouch status updated successfully",
            "retouch_request_number": rrp.retouch_request.RequestNumber,
            "barcode": rrp.st_request_product.product.barcode,
            "retouch_status": rrp.retouch_status.name if rrp.retouch_status else None,
            "retouch_link": rrp.retouch_link
        }, status=status.HTTP_200_OK)


class UpdateSRetouchStatusView(APIView):
    """
    POST /ft/sr/update-sretouch-status/
    body: {
      "request_number": 123,
      "barcode": "1234567890123",
      "sretouch_status_id": 1 or 2,
      "comment": "Описание правок" (опционально)
    }
    Если sretouch_status_id=1 (Проверено), проверяем, не остались ли null или ≠1 у товаров.
    Если все стали 1 => ставим RetouchRequest.status_id=5 (или под вашу логику).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = SRetouchStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rrp = serializer.save()  # RetouchRequestProduct

        # Если sretouch_status == 1 ("Проверено"), проверяем все товары
        if rrp.sretouch_status_id == 1:
            retouch_request = rrp.retouch_request
            all_products = retouch_request.retouch_products.all()

            # Проверяем, что нет null: sretouch_status_id IS NOT NULL
            # и нет значений ≠1
            # Если всё 1 => ставим retouch_request.status_id=5 (к примеру)
            if (all_products.exists() and
                all_products.filter(sretouch_status_id__isnull=True).count() == 0 and
                all_products.exclude(sretouch_status_id=1).count() == 0):

                # Меняем статус заявки
                try:
                    new_status = RetouchRequestStatus.objects.get(id=5)
                    retouch_request.status = new_status
                    retouch_request.save(update_fields=["status"])
                except RetouchRequestStatus.DoesNotExist:
                    pass

        return Response({
            "detail": "SRetouch status updated successfully",
            "retouch_request_number": rrp.retouch_request.RequestNumber,
            "barcode": rrp.st_request_product.product.barcode,
            "sretouch_status": rrp.sretouch_status.name if rrp.sretouch_status else None,
            "comment": rrp.comment
        }, status=status.HTTP_200_OK)

class ReadyPhotosListView(generics.ListAPIView):
    serializer_class = ReadyPhotosSerializer
    pagination_class = ReadyPhotosPagination

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]

    # Разрешённые поля для сортировки:
    ordering_fields = [
        'st_request_product__product__barcode',
        'st_request_product__product__name',
        'st_request_product__product__seller',
        'retouch_request__creation_date',
        'retouch_link',
    ]
    ordering = ['-retouch_request__creation_date']
    search_fields = [
        'st_request_product__product__barcode',
        'st_request_product__product__name',
    ]

    def get_queryset(self):
        qs = RetouchRequestProduct.objects.filter(
            retouch_status_id=2,
            sretouch_status_id=1
        ).select_related(
            'retouch_request',
            'st_request_product__product',
            'st_request_product__request'  # Для доступа к полю photo_date модели STRequest
        )

        # Фильтрация по штрихкодам:
        barcodes_str = self.request.query_params.get('barcodes')
        if barcodes_str:
            bc_list = [b.strip() for b in barcodes_str.split(',') if b.strip()]
            qs = qs.filter(st_request_product__product__barcode__in=bc_list)

        # Фильтрация по магазинам (поддержка нескольких значений через запятую):
        seller_str = self.request.query_params.get('seller')
        if seller_str:
            seller_list = [s.strip() for s in seller_str.split(',') if s.strip()]
            qs = qs.filter(st_request_product__product__seller__in=seller_list)

        # Фильтрация по диапазону дат (photo_date из модели STRequest)
        date_from_str = self.request.query_params.get('date_from')
        date_to_str = self.request.query_params.get('date_to')
        if date_from_str and date_to_str:
            try:
                date_from = datetime.strptime(date_from_str, "%d.%m.%Y")
                date_to = datetime.strptime(date_to_str, "%d.%m.%Y")
                # Сдвигаем дату конца на 1 день, чтобы включить её в диапазон
                date_to = date_to + timedelta(days=1)
                qs = qs.filter(
                    st_request_product__request__photo_date__gte=date_from,
                    st_request_product__request__photo_date__lt=date_to
                )
            except ValueError:
                # Если формат даты неверный, можно добавить обработку ошибки
                pass

        return qs

    def list(self, request, *args, **kwargs):
        # Получаем отсортированный, отфильтрованный queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Если переданы штрихкоды, вычисляем отсутствующие:
        barcodes_str = request.query_params.get('barcodes')
        not_found = []
        if barcodes_str:
            bc_list = [b.strip() for b in barcodes_str.split(',') if b.strip()]
            # Получаем найденные штрихкоды:
            found_barcodes = list(queryset.values_list('st_request_product__product__barcode', flat=True).distinct())
            # Определяем, какие штрихкоды не найдены:
            not_found = [b for b in bc_list if b not in found_barcodes]

        # Применяем пагинацию, если она настроена:
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(queryset, many=True)
            response_data = serializer.data

        # Добавляем в ответ массив not_found, если фильтрация по штрихкодам была:
        if barcodes_str:
            if isinstance(response_data, dict):
                response_data['not_found'] = not_found
            else:
                response_data = {
                    'results': response_data,
                    'not_found': not_found
                }

        return Response(response_data)

class SRStatisticView(APIView):
    """
    GET /ft/sr-statistic/?date=YYYY-MM-DD
    Выдаёт список пользователей (ретушеров) и кол-во обработанных 
    (retouch_status=2 и sretouch_status=1) продуктов на заданную дату.
    Дата проверяется по RetouchRequest.retouch_date.
    Сортируем по first_name, last_name.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Считываем параметр date
        date_str = request.query_params.get('date')  # "YYYY-MM-DD"
        if not date_str:
            return Response({"error": "Parameter 'date' is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format, expected YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Фильтруем RetouchRequestProduct:
        # retouch_status=2 (Готов), sretouch_status=1 (Проверено),
        # retouch_request.retouch_date__date = date_obj и retouch_request.status_id=5.
        qs = RetouchRequestProduct.objects.filter(
            retouch_status_id=2,
            sretouch_status_id=1,
            retouch_request__retouch_date__date=date_obj,
            retouch_request__status_id=5  # добавлено условие по статусу = 5
        ).select_related("retouch_request__retoucher")

        # Исключаем случаи без ретушёра, если это необходимо
        qs = qs.exclude(retouch_request__retoucher__isnull=True)

        # Группируем по ретушёру (User), считаем количество записей
        user_qs = qs.values(
            "retouch_request__retoucher__id",
            "retouch_request__retoucher__first_name",
            "retouch_request__retoucher__last_name",
        ).annotate(
            done_count=Count("id")
        )

        # Превращаем в список и сортируем по first_name, last_name
        user_list = list(user_qs)
        user_list.sort(key=lambda x: (
            x["retouch_request__retoucher__first_name"] or "", 
            x["retouch_request__retoucher__last_name"] or "",
        ))

        # Формируем результат
        result = []
        for row in user_list:
            uid = row["retouch_request__retoucher__id"]
            fn  = row["retouch_request__retoucher__first_name"] or ""
            ln  = row["retouch_request__retoucher__last_name"]  or ""
            cnt = row["done_count"]

            result.append({
                "user_id": uid,
                "first_name": fn,
                "last_name": ln,
                "count": cnt,
            })

        return Response(result, status=status.HTTP_200_OK)

def stockman_income(request):
    """
    Эндпоинт для приемки товара (operation type = 3, move_status = 3).
    - Для каждого штрихкода из запроса:
      * Проставляем move_status=3
      * Заполняем income_date текущей датой
      * Заполняем income_stockman пользователем из запроса
      * Создаем запись в ProductOperation (operation_type=3)
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer = StockmanIncomeSerializer(data=request.data)
    if serializer.is_valid():
        barcodes = serializer.validated_data['barcodes']
        products = Product.objects.filter(barcode__in=barcodes)

        if not products:
            return Response(
                {"detail": "По переданным штрихкодам товары не найдены."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Обновляем поля в модели Product
        for product in products:
            product.move_status_id = 3  # move_status = 3 (Приемка)
            product.income_date = timezone.now()
            product.income_stockman = request.user
            product.save()

        # Создаем записи в ProductOperation
        for product in products:
            ProductOperation.objects.create(
                product=product,
                operation_type_id=3,  # Тип операции 3 для приход
                user=request.user,
                date=timezone.now()  # Можно не указывать, auto_now_add в модели
            )

        return Response({"detail": "Товары успешно приняты."}, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def stockman_outcome(request):
    """
    Эндпоинт для отправки товара (operation type = 4, move_status = 4).
    - Для каждого штрихкода из запроса:
      * Проставляем move_status=4
      * Заполняем outcome_date текущей датой
      * Заполняем outcome_stockman пользователем из запроса
      * Создаем запись в ProductOperation (operation_type=4)
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer = StockmanOutcomeSerializer(data=request.data)
    if serializer.is_valid():
        barcodes = serializer.validated_data['barcodes']
        products = Product.objects.filter(barcode__in=barcodes)

        if not products:
            return Response(
                {"detail": "По переданным штрихкодам товары не найдены."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Обновляем поля в модели Product
        for product in products:
            product.move_status_id = 4  # move_status = 4 (Отправка)
            product.outcome_date = timezone.now()
            product.outcome_stockman = request.user
            product.save()

        # Создаем записи в ProductOperation
        for product in products:
            ProductOperation.objects.create(
                product=product,
                operation_type_id=4,  # Тип операции 4 для расход
                user=request.user,
                date=timezone.now()
            )

        return Response({"detail": "Товары успешно отправлены."}, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def stockman_defect(request):
    """
    Эндпоинт для пометки товара как брак (operation type = 25, move_status = 25).
    - В запросе штрихкод и комментарий
    - Для товара:
      * move_status=25
    - Создаем запись в ProductOperation (operation_type=25, comment=переданный)
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer = StockmanDefectSerializer(data=request.data)
    if serializer.is_valid():
        barcode = serializer.validated_data['barcode']
        comment = serializer.validated_data.get('comment', '')

        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return Response(
                {"detail": f"Товар со штрихкодом {barcode} не найден."},
                status=status.HTTP_404_NOT_FOUND
            )

        product.move_status_id = 25
        product.save()

        ProductOperation.objects.create(
            product=product,
            operation_type_id=25,
            user=request.user,
            date=timezone.now(),
            comment=comment
        )

        return Response({"detail": "Товар помечен как брак."}, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def stockman_opened(request):
    """
    Эндпоинт для пометки товара как вскрыто (operation type = 30).
    - В запросе штрихкод
    - Создаем запись в ProductOperation (operation_type=30, comment="Вскрыто")
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer = StockmanOpenedSerializer(data=request.data)
    if serializer.is_valid():
        barcode = serializer.validated_data['barcode']

        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return Response(
                {"detail": f"Товар со штрихкодом {barcode} не найден."},
                status=status.HTTP_404_NOT_FOUND
            )

        ProductOperation.objects.create(
            product=product,
            operation_type_id=30,
            user=request.user,
            date=timezone.now(),
            comment="Вскрыто"
        )

        return Response({"detail": "Товар помечен как вскрыто."}, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def get_next_request_number() -> str:
    """
    Возвращает следующий номер заявки (строка длиной 13 символов с ведущими нулями).
    Если записей нет, начинаем с '0000000000001'.
    Предполагаем, что в RequestNumber хранятся только цифры в виде строки.
    """
    max_number = STRequest.objects.aggregate(max_num=Max('RequestNumber'))['max_num']
    if max_number is None:
        # Если еще ни одной заявки нет
        return "0000000000001"
    try:
        # Пробуем интерпретировать существующий макс. номер как число
        next_num_int = int(max_number) + 1
    except ValueError:
        # Если вдруг в базе окажется не-числовая строка,
        # можно либо сгенерировать ошибку, либо начать с 1.
        next_num_int = 1
    # Преобразуем в строку, дополненную нулями до длины 13
    return str(next_num_int).zfill(13)

def strequest_create(request):
    """
    Эндпоинт для создания новой заявки STRequest.
      - Номер RequestNumber формируется автоматически
      - creation_date ставится текущая (если auto_now_add=True в модели, он сам заполнится)
      - stockman = request.user
      - status = 1
    В ответе возвращается созданный RequestNumber.
    """
    serializer = STRequestCreateSerializer(data=request.data)
    if serializer.is_valid():
        # Генерируем номер заявки
        next_request_number = get_next_request_number()

        # Создаем заявку, применяя поля из сериалайзера
        strequest = STRequest.objects.create(
            RequestNumber=next_request_number,
            # creation_date=timezone.now(),  # Не обязательно, если auto_now_add=True
            stockman=request.user,           # Запоминаем, кто создал
            **serializer.validated_data
        )

        # Принудительно устанавливаем статус = 1
        # Предполагаем, что такая запись (ID=1) в STRequestStatus существует.
        try:
            strequest.status = STRequestStatus.objects.get(pk=1)
        except STRequestStatus.DoesNotExist:
            return Response(
                {"detail": "Статус с ID=1 не найден в STRequestStatus."},
                status=status.HTTP_400_BAD_REQUEST
            )
        strequest.save()
        
        # Возвращаем номер заявки
        return Response(
            {"RequestNumber": strequest.RequestNumber},
            status=status.HTTP_201_CREATED
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def nofoto_create(request):
    """
    Эндпоинт для фиксации 'нет фото' по конкретному товару (по штрихкоду).
    
    Шаги:
    1. Создание записи в Nofoto (товар, текущая дата, user).
    2. Поиск в STRequestProduct всех позиций, где:
       - Товар = наш Product
       - STRequest в статусе 3
       Удалить каждую из них, при этом перед удалением
       добавить запись в STRequestHistory (operation=2).
    """
    serializer = NofotoCreateSerializer(data=request.data)
    if serializer.is_valid():
        barcode = serializer.validated_data['barcode']

        # Ищем товар по штрихкоду
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            return Response(
                {"detail": f"Товар со штрихкодом {barcode} не найден."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 1. Создаём запись в Nofoto
        Nofoto.objects.create(
            product=product,
            user=request.user,
            # date не указываем вручную, т.к. auto_now_add=True
        )

        # 2. Удаляем позиции из STRequestProduct, где STRequest в статусе 3.
        #    Перед удалением сохраняем запись в STRequestHistory.
        
        strequest_products_qs = STRequestProduct.objects.filter(
            product=product,
            request__status_id=3
        )

        # Опционально: если нужно проверить, что есть хотя бы одна такая запись
        # if not strequest_products_qs.exists():
        #     pass  # Либо вернуть предупреждение, либо ничего

        # Убедимся, что операция с ID=2 существует
        # (если уверены, что существует — можно пропустить проверку)
        try:
            operation_del = STRequestHistoryOperations.objects.get(pk=2)
        except STRequestHistoryOperations.DoesNotExist:
            return Response(
                {"detail": "Не найдена операция STRequestHistoryOperations c ID=2."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Для каждой строки strequestproduct создаём запись в истории
        for strequestproduct in strequest_products_qs:
            STRequestHistory.objects.create(
                st_request=strequestproduct.request,
                product=strequestproduct.product,
                user=request.user,
                # date = timezone.now(),  # можно указать явно, но в модели стоит auto_now_add
                operation=operation_del
            )

        # После записи в историю удаляем из STRequestProduct
        strequest_products_qs.delete()

        return Response({"detail": "Запись Nofoto создана, товары удалены из STRequestProduct, история обновлена."},
                        status=status.HTTP_200_OK)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Если нужна авторизация, можно поменять/убрать
def sp_get_assistants(request):
    """
    Возвращает список пользователей, состоящих в группе "Ассистент".
    Формат ответа:
    [
      {
        "id": <int>,
        "first_name": <str>,
        "last_name": <str>
      },
      ...
    ]
    """
    try:
        assistants_group = Group.objects.get(name="Ассистент")
    except Group.DoesNotExist:
        return Response({"detail": "Группа 'Ассистент' не найдена."},
                        status=status.HTTP_404_NOT_FOUND)
    
    users = assistants_group.user_set.all()
    data = [
        {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        for user in users
    ]
    return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sp_assign_assistant(request):
    """
    Назначение пользователя (id) в качестве assistant по номеру заявки (RequestNumber).
    В теле запроса ожидаются поля: {"strequest": "<RequestNumber>", "user": <id>}
    
    При назначении устанавливается текущее время (assistant_date).
    """
    request_number = request.data.get('strequest')
    user_id = request.data.get('user')

    if not request_number or not user_id:
        return Response(
            {"detail": "Поля 'strequest' и 'user' обязательны."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        strequest = STRequest.objects.get(RequestNumber=request_number)
    except STRequest.DoesNotExist:
        return Response(
            {"detail": f"Заявка с номером '{request_number}' не найдена."},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"detail": f"Пользователь с id '{user_id}' не найден."},
                        status=status.HTTP_404_NOT_FOUND)

    strequest.assistant = user
    strequest.assistant_date = timezone.now()  # Установка текущего времени
    strequest.save()

    return Response(
        {"detail": f"Пользователь (id={user_id}) назначен ассистентом."},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sp_clear_assistant(request):
    """
    Очистка полей 'assistant' и 'assistant_date'.
    В теле запроса ожидается поле: {"strequest": "<RequestNumber>"}
    """
    request_number = request.data.get('strequest')

    if not request_number:
        return Response(
            {"detail": "Поле 'strequest' обязательно."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        strequest = STRequest.objects.get(RequestNumber=request_number)
    except STRequest.DoesNotExist:
        return Response(
            {"detail": f"Заявка с номером '{request_number}' не найдена."},
            status=status.HTTP_404_NOT_FOUND
        )

    strequest.assistant = None
    strequest.assistant_date = None
    strequest.save()

    return Response(
        {"detail": "Поле 'assistant' и 'assistant_date' очищены."},
        status=status.HTTP_200_OK
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Если нужна авторизация
def sp_daily_stats(request):
    """
    Эндпоинт для получения статистики по фотографам и ассистентам за указанную дату.
    
    Параметры:
      ?date=dd.mm.yyyy

    Возвращает:
      {
        "photographers": [
          "Имя Фамилия - число",
          ...
        ],
        "assistants": [
          "Имя Фамилия - число",
          ...
        ]
      }
    """
    date_str = request.GET.get('date')
    if not date_str:
        return Response(
            {"detail": "Параметр 'date' (dd.mm.yyyy) обязателен."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Пытаемся распарсить дату из формата dd.mm.yyyy
    try:
        day, month, year = map(int, date_str.split('.'))
        stats_date = datetime(year, month, day)
    except (ValueError, TypeError):
        return Response(
            {"detail": "Некорректный формат даты. Ожидается dd.mm.yyyy"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # ----------------------------------------------------------------------------
    # 1. ФОТОГРАФЫ
    # ----------------------------------------------------------------------------
    # Фильтруем заявки, у которых date (только год, месяц, день) совпадает с photo_date
    # И у которых есть фотограф photographer.
    # Для каждой такой заявки суммируем товары с photo_status ∈ [1,2,25] и sphoto_status=1.
    # Затем группируем по фотографу.

    photographers_data = {}
    # Список нужных заявок
    photographer_requests = STRequest.objects.filter(
        photo_date__year=stats_date.year,
        photo_date__month=stats_date.month,
        photo_date__day=stats_date.day
    ).exclude(photographer=None)

    # Подтягиваем связанные продукты одним запросом
    # (select_related/ prefetch_related по необходимости)
    for streq in photographer_requests.prefetch_related('strequestproduct_set', 'photographer'):
        if not streq.photographer:
            continue
        ph = streq.photographer
        # Подсчёт количества товаров в этой заявке
        # photo_status ∈ [1,2,25], sphoto_status=1
        count_products = STRequestProduct.objects.filter(
            request=streq,
            photo_status__id__in=[1, 2, 25],
            sphoto_status__id=1
        ).count()

        # накапливаем в dict
        if ph.id not in photographers_data:
            photographers_data[ph.id] = {
                "user": ph,
                "count": 0
            }
        photographers_data[ph.id]["count"] += count_products

    # Формируем итоговый список
    photographers_result = []
    for ph_id, val in photographers_data.items():
        user = val["user"]
        total = val["count"]
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        photographers_result.append(f"{first_name} {last_name} - {total}")

    # ----------------------------------------------------------------------------
    # 2. АССИСТЕНТЫ
    # ----------------------------------------------------------------------------
    # Смотрим заявки, у которых assistant_date (год/месяц/день) = stats_date
    # и есть ассистент. По каждой заявке считаем ВСЕ товары (STRequestProduct.count)
    # Группируем по ассистенту, суммируем.

    assistants_data = {}
    assistant_requests = STRequest.objects.filter(
        assistant_date__year=stats_date.year,
        assistant_date__month=stats_date.month,
        assistant_date__day=stats_date.day
    ).exclude(assistant=None)

    for streq in assistant_requests.prefetch_related('strequestproduct_set', 'assistant'):
        if not streq.assistant:
            continue
        asst = streq.assistant
        # Подсчёт всех товаров в заявке
        count_products = STRequestProduct.objects.filter(request=streq).count()

        if asst.id not in assistants_data:
            assistants_data[asst.id] = {
                "user": asst,
                "count": 0
            }
        assistants_data[asst.id]["count"] += count_products

    # Формируем итоговый список
    assistants_result = []
    for asst_id, val in assistants_data.items():
        user = val["user"]
        total = val["count"]
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        assistants_result.append(f"{first_name} {last_name} - {total}")

    # ----------------------------------------------------------------------------
    # Итоговый ответ
    # ----------------------------------------------------------------------------
    response_data = {
        "photographers": photographers_result,
        "assistants": assistants_result
    }
    return Response(response_data, status=status.HTTP_200_OK)

class ProductOperationHistoryNew(PageNumberPagination):
    page_size = 50  # можно настроить размер страницы
    page_size_query_param = 'page_size'
    max_page_size = 999999

class ProductOperationListView(generics.ListAPIView):
    queryset = ProductOperation.objects.select_related('product', 'operation_type', 'user').all()
    serializer_class = ProductOperationSerializer
    pagination_class = ProductOperationHistoryNew
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ProductOperationFilter
    ordering_fields = [
        'product__barcode',
        'product__name',
        'product__seller',
        'operation_type__name',
        'user__first_name',
        'date',
        'comment',
    ]
    ordering = ['-date']

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data).data
        else:
            serializer = self.get_serializer(qs, many=True)
            response_data = serializer.data

        if 'barcode' in request.query_params:
            barcode_param = request.query_params.get('barcode')
            barcodes_requested = [b.strip() for b in barcode_param.split(',') if b.strip()]
            found_barcodes = list(qs.values_list('product__barcode', flat=True).distinct())
            not_found = [b for b in barcodes_requested if b not in found_barcodes]
            response_data['not_found_barcodes'] = not_found

        return Response(response_data)


class ProductOperationTypesListView(generics.ListAPIView):
    queryset = ProductOperationTypes.objects.all()
    serializer_class = ProductOperationTypesSerializer
    pagination_class = None
    ordering = ['id']
