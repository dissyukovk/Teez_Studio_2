from rest_framework.views import APIView
from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Exists, OuterRef, Min, Count, Q, Value, BooleanField, F, Case, When, Subquery
from django.db.models.functions import Coalesce
from django.contrib.auth.models import User, Group
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django_q.tasks import async_task
from datetime import datetime, timedelta

from core.models import (
    UserProfile,
    STRequest,
    STRequestProduct,
    STRequestStatus,
    Product,
    ProductCategory,
    PhotoStatus,
    SPhotoStatus,
    Nofoto,
    ProductOperationTypes,
    ProductOperation
    )
from .serializers import (
    STRequestListSerializer,
    UserFullNameSerializer,
    STRequestDetailSerializer,
    STRequestProductDetailSerializer
    )
from .pagination import StandardResultsSetPagination
from .filters import STRequestFilter


# Helper function for permission check (can be moved to a common utils or permissions file)
def is_senior_photographer(user):
    """
    Checks if the given user belongs to the 'Старший фотограф' group.
    """
    if user.is_anonymous:
        return False
    try:
        # Make sure the group name matches exactly what's in your database.
        senior_photographer_group = Group.objects.get(name='Старший фотограф')
        return senior_photographer_group in user.groups.all()
    except Group.DoesNotExist:
        # If the group doesn't exist, then no user can be a member.
        return False

#список заявок со статусом создана
class STRequest2ListView(generics.ListAPIView):
    """
    API эндпоинт для получения списка заявок (STRequest) с кастомной сортировкой,
    фильтрацией, пагинацией и форматированием вывода.
    Требует аутентификации пользователя.
    """
    serializer_class = STRequestListSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = STRequestFilter

    def get_queryset(self):
        queryset = STRequest.objects.filter(status_id=2)

        priority_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            product__priority=True
        )
        queryset = queryset.annotate(
            has_priority_product=Exists(priority_subquery)
        )

        # Ensure very_far_date is timezone-aware if USE_TZ is True
        very_far_date = timezone.make_aware(datetime(9999, 12, 31, 23, 59, 59))
        queryset = queryset.annotate(
            min_income_date_raw=Min('strequestproduct__product__income_date')
        ).annotate(
            min_income_date=Coalesce('min_income_date_raw', Value(very_far_date))
        )

        info_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            product__info__isnull=False
        ).exclude(product__info='')
        queryset = queryset.annotate(
            has_product_with_info=Exists(info_subquery)
        )

        queryset = queryset.annotate(
            total_products_count=Count('strequestproduct')
        )

        for_check_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            photo_status_id__in=[1, 2, 25]
        ).exclude(
            sphoto_status_id=1
        ).values('request').annotate(count=Count('id')).values('count')
        
        # ✨ Apply the for_check_count_annotation
        queryset = queryset.annotate(
            for_check_count_annotation=Coalesce(Subquery(for_check_subquery), 0)
        )

        queryset = queryset.order_by(
            F('has_priority_product').desc(),
            F('min_income_date').asc()
        )

        queryset = queryset.select_related(
            'photographer',
            'stockman',
            'assistant',
            'status'
        )
        
        queryset = queryset.prefetch_related('strequestproduct_set')

        st_type_param = self.request.query_params.get('strequest_type')
        if st_type_param:
            type_ids = [int(x) for x in st_type_param.split(',') if x.strip().isdigit()]
            if type_ids:
                queryset = queryset.filter(STRequestType_id__in=type_ids)

        return queryset

#список заявок со статусом на съемке
class STRequest3ListView(generics.ListAPIView):
    """
    API эндпоинт для получения списка заявок (STRequest) со статусом "на съемке".
    """
    serializer_class = STRequestListSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = STRequestFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = STRequest.objects.filter(status_id=3)

        priority_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            product__priority=True
        )
        queryset = queryset.annotate(
            has_priority_product=Exists(priority_subquery)
        )

        very_far_date = timezone.make_aware(datetime(9999, 12, 31, 23, 59, 59))
        queryset = queryset.annotate(
            min_income_date_raw=Min('strequestproduct__product__income_date')
        ).annotate(
            min_income_date=Coalesce('min_income_date_raw', Value(very_far_date))
        )

        info_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            product__info__isnull=False
        ).exclude(product__info='')
        queryset = queryset.annotate(
            has_product_with_info=Exists(info_subquery)
        )

        queryset = queryset.annotate(
            total_products_count=Count('strequestproduct')
        )

        for_check_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            photo_status_id__in=[1, 2, 25]
        ).exclude(
            sphoto_status_id=1
        ).values('request').annotate(count=Count('id')).values('count')

        # ✨ Apply the for_check_count_annotation
        queryset = queryset.annotate(
            for_check_count_annotation=Coalesce(Subquery(for_check_subquery), 0)
        )

        queryset = queryset.order_by(
            F('has_priority_product').desc(),
            F('min_income_date').asc()
        )

        queryset = queryset.select_related(
            'photographer',
            'stockman',
            'assistant',
            'status'
        )
        
        queryset = queryset.prefetch_related('strequestproduct_set')

        return queryset
    
#список заявок со статусом отснято
class STRequest5ListView(generics.ListAPIView):
    """
    API эндпоинт для получения списка заявок (STRequest) со статусом "отснято",
    где photo_date было менее 24 часов назад.
    """
    serializer_class = STRequestListSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = STRequestFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = STRequest.objects.filter(status_id=5)

        # ✨ Filter for photo_date within the last 24 hours
        status5_treshold = timezone.now() - timedelta(hours=24)
        queryset = queryset.filter(photo_date__gte=status5_treshold) # photo_date must be greater than or equal to 24 hours ago

        priority_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            product__priority=True
        )
        queryset = queryset.annotate(
            has_priority_product=Exists(priority_subquery)
        )

        very_far_date = timezone.make_aware(datetime(9999, 12, 31, 23, 59, 59))
        queryset = queryset.annotate(
            min_income_date_raw=Min('strequestproduct__product__income_date')
        ).annotate(
            min_income_date=Coalesce('min_income_date_raw', Value(very_far_date))
        )

        info_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            product__info__isnull=False
        ).exclude(product__info='')
        queryset = queryset.annotate(
            has_product_with_info=Exists(info_subquery)
        )

        queryset = queryset.annotate(
            total_products_count=Count('strequestproduct')
        )

        for_check_subquery = STRequestProduct.objects.filter(
            request=OuterRef('pk'),
            photo_status_id__in=[1, 2, 25]
        ).exclude(
            sphoto_status_id=1
        ).values('request').annotate(count=Count('id')).values('count')

        # ✨ Apply the for_check_count_annotation
        queryset = queryset.annotate(
            for_check_count_annotation=Coalesce(Subquery(for_check_subquery), 0)
        )
        
        queryset = queryset.order_by(
            F('has_priority_product').desc(),
            F('min_income_date').asc()
        )

        queryset = queryset.select_related(
            'photographer',
            'stockman',
            'assistant',
            'status'
        )
        
        queryset = queryset.prefetch_related('strequestproduct_set')

        return queryset

#Получение списка фотографов на смене
class WorkingPhotographerListView(generics.ListAPIView):
    """
    API эндпоинт для получения списка пользователей из группы 'Фотограф',
    у которых в профиле on_work=True.
    Без пагинации, фильтрации и сортировки.
    Требует аутентификации.
    """
    serializer_class = UserFullNameSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None # <--- Отключаем пагинацию

    def get_queryset(self):
        """
        Возвращает queryset пользователей, соответствующих критериям:
        - Состоит в группе 'Фотограф'.
        - Имеет связанный UserProfile с on_work=True.
        """
        # Фильтруем пользователей по имени группы и флагу on_work в связанном профиле
        # profile__on_work=True использует related_name='profile' из UserProfile.user
        queryset = User.objects.filter(
            groups__name='Фотограф',  # Указываем имя группы
            profile__on_work=True     # Фильтруем по полю в связанной модели UserProfile
        ).distinct() # distinct() на случай, если пользователь как-то оказался в группе >1 раза

        return queryset
    
#Получение списка ассистентов
class AssistantsListView(generics.ListAPIView):
    """
    API эндпоинт для получения списка пользователей из группы 'Фотограф',
    у которых в профиле on_work=True.
    Без пагинации, фильтрации и сортировки.
    Требует аутентификации.
    """
    serializer_class = UserFullNameSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None # <--- Отключаем пагинацию

    def get_queryset(self):
        """
        Возвращает queryset пользователей, соответствующих критериям:
        - Состоит в группе 'ассистент'.
        """
        # Фильтруем пользователей по имени группы и флагу on_work в связанном профиле
        queryset = User.objects.filter(
            groups__name='Ассистент',  # Указываем имя группы
        ).distinct() # distinct() на случай, если пользователь как-то оказался в группе >1 раза

        return queryset

#Назначение фотографа
class AssignPhotographerView(views.APIView):
    """
    Эндпоинт для назначения фотографа на заявку STRequest.
    Принимает POST запрос с request_number и user_id.
    Обновляет заявку, устанавливая фотографа, статус 3 и дату назначения.
    Создает записи в ProductOperation для каждого товара в заявке.
    Отправляет уведомления в Telegram.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        request_number = request.data.get('request_number')
        user_id = request.data.get('user_id')

        # --- Валидация входных данных ---
        if not request_number:
            return Response(
                {"error": "Необходимо указать 'request_number'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not user_id:
            return Response(
                {"error": "Необходимо указать 'user_id'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            user_id = int(user_id)
        except ValueError:
            return Response(
                {"error": "'user_id' должен быть целым числом."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Получение объектов из БД ---
        st_request = get_object_or_404(STRequest, RequestNumber=request_number)
        photographer = get_object_or_404(User, id=user_id)

        # Опционально: Проверка, что пользователь действительно фотограф
        if not photographer.groups.filter(name='Фотограф').exists():
            return Response(
                {"error": f"Пользователь {photographer.username} не состоит в группе 'Фотограф'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Обновление заявки ---
        st_request.photographer = photographer
        # Убедитесь, что у вас есть статус с ID=3 или используйте st_request.status = get_object_or_404(STRequestStatus, id=3)
        st_request.status_id = 3 # Устанавливаем ID статуса напрямую
        st_request.photo_date = timezone.now()
        st_request.save(update_fields=['photographer', 'status_id', 'photo_date'])

        # --- Создание записей в ProductOperation ---
        # Получаем тип операции "Назначение фотографа" (предполагаем ID=5)
        try:
            operation_type_assign_photographer = ProductOperationTypes.objects.get(id=5)
        except ProductOperationTypes.DoesNotExist:
            # Обработка случая, если тип операции с ID=5 не найден.
            # Можно вернуть ошибку или создать его, если это допустимо.
            # В данном случае, вернем ошибку, т.к. это критичный справочник.
            return Response(
                {"error": "Тип операции с ID=5 (Назначение фотографа) не найден в ProductOperationTypes."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR # Или другой подходящий статус
            )

        # Получаем все товары, связанные с этой заявкой
        products_in_request = STRequestProduct.objects.filter(request=st_request).select_related('product')

        operations_to_create = []
        current_time = timezone.now() # Используем одно и то же время для всех операций в рамках одного запроса

        for st_request_product_item in products_in_request:
            operations_to_create.append(
                ProductOperation(
                    product=st_request_product_item.product,
                    operation_type=operation_type_assign_photographer,
                    user=photographer, # Юзер, которому происходит назначение
                    # date устанавливается автоматически через auto_now_add,
                    # но если нужно точное время назначения, а не создания записи:
                    # date=current_time, # Раскомментируйте, если date не auto_now_add или нужно конкретное время
                    comment=st_request.RequestNumber # Номер заявки STRequestNumber
                )
            )

        if operations_to_create:
            ProductOperation.objects.bulk_create(operations_to_create)
        # --- Конец создания записей в ProductOperation ---

        # --- Подготовка данных для Telegram ---
        user_profile = UserProfile.objects.filter(user=photographer).first()
        photographer_telegram_id = user_profile.telegram_id if user_profile else None

        products_with_info = STRequestProduct.objects.filter(
            request=st_request,
            product__info__isnull=False
        ).exclude(
            product__info__exact=''
        ).select_related('product')

        info_lines = []
        if products_with_info.exists():
            for item in products_with_info:
                info_lines.append(f"{item.product.barcode} - {item.product.info}")
        info_details = "\n".join(info_lines)

        # --- Отправка сообщений ---
        if photographer_telegram_id:
            photographer_message = f"Вам назначена заявка {st_request.RequestNumber}"
            if info_details:
                photographer_message += f"\n\n*Товары с инфо:*\n{info_details}"
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=photographer_telegram_id,
                text=photographer_message
            )

        if info_details:
            group_chat_id = "-1002559221974" # Рекомендуется вынести в настройки
            group_thread_id = 2              # Рекомендуется вынести в настройки
            group_message = f"*Назначены товары с инфо для заявки {st_request.RequestNumber}:*\n{info_details}"
            async_task(
                'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                chat_id=group_chat_id,
                text=group_message,
                message_thread_id=group_thread_id
            )

        return Response(
            {"message": f"Фотограф {photographer.username} назначен на заявку {st_request.RequestNumber}. Операции по товарам созданы."},
            status=status.HTTP_200_OK
        )

#сброс фотографа
class RemovePhotographerView(views.APIView):
    """
    Эндпоинт для снятия фотографа с заявки STRequest.
    Принимает POST запрос с request_number.
    Очищает поля photographer и photo_date, устанавливает статус 2.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        request_number = request.data.get('request_number')

        # --- Валидация входных данных ---
        if not request_number:
            return Response(
                {"error": "Необходимо указать 'request_number'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Получение объекта из БД ---
        st_request = get_object_or_404(STRequest, RequestNumber=request_number)

        # --- Опциональная проверка: имеет смысл снимать фотографа, если он назначен (статус 3) ---
        if st_request.status_id != 3:
             return Response(
                 {"error": f"Нельзя снять фотографа с заявки {request_number}, так как она не в статусе На съемке."},
                 status=status.HTTP_400_BAD_REQUEST
             )
        # Или можно просто проверить наличие фотографа:
        if not st_request.photographer:
             return Response(
                 {"warning": f"На заявке {request_number} фотограф уже не назначен."},
                 # Можно вернуть 200 OK, так как состояние уже соответствует желаемому,
                 # или 400 Bad Request, если это считается ошибкой вызова.
                 # Вернем 200 OK и сам объект заявки.
                 status=status.HTTP_200_OK,
                 data=STRequestListSerializer(st_request).data
             )


        # --- Обновление заявки ---
        st_request.photographer = None # Очищаем поле фотографа
        st_request.photo_date = None   # Очищаем дату назначения
        st_request.status_id = 2       # Устанавливаем статус ID=2 (например, "Ожидает назначения")

        # Сохраняем только измененные поля для эффективности
        st_request.save(update_fields=['photographer', 'status_id', 'photo_date'])

        # --- Формирование ответа ---
        # Сериализуем обновленный объект заявки для ответа
        serializer = STRequestListSerializer(st_request)
        return Response(status=status.HTTP_200_OK)

# Назначить ассистента
class AssignAssistantView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not is_senior_photographer(request.user):
            return Response(
                {"error": "Доступ запрещен. Только 'Старший фотограф' может выполнять это действие."},
                status=status.HTTP_403_FORBIDDEN
            )

        request_number = request.data.get('request_number')
        user_id = request.data.get('user_id')

        if not request_number:
            return Response({"error": "Необходимо указать 'request_number'."}, status=status.HTTP_400_BAD_REQUEST)
        if not user_id:
            return Response({"error": "Необходимо указать 'user_id'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_id = int(user_id)
        except ValueError:
            return Response({"error": "'user_id' должен быть целым числом."}, status=status.HTTP_400_BAD_REQUEST)

        st_request = get_object_or_404(STRequest, RequestNumber=request_number)
        assistant_user = get_object_or_404(User, id=user_id)

        # Optional: Check if the user is in 'Ассистент' group
        # if not assistant_user.groups.filter(name='Ассистент').exists():
        #     return Response(
        #         {"error": f"Пользователь {assistant_user.username} не является ассистентом."},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )

        st_request.assistant = assistant_user
        st_request.assistant_date = timezone.now()
        st_request.save(update_fields=['assistant', 'assistant_date'])

        # serializer = STRequestListSerializer(st_request) # Return the updated request
        return Response(
            {"message": f"Ассистент {assistant_user.username} назначен на заявку {st_request.RequestNumber}."},
            status=status.HTTP_200_OK
        )

#Сброс ассистента
class RemoveAssistantView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not is_senior_photographer(request.user):
            return Response(
                {"error": "Доступ запрещен. Только 'Старший фотограф' может выполнять это действие."},
                status=status.HTTP_403_FORBIDDEN
            )

        request_number = request.data.get('request_number')
        if not request_number:
            return Response({"error": "Необходимо указать 'request_number'."}, status=status.HTTP_400_BAD_REQUEST)

        st_request = get_object_or_404(STRequest, RequestNumber=request_number)

        if not st_request.assistant:
            return Response(
                {"warning": f"На заявке {request_number} ассистент уже не назначен."},
                status=status.HTTP_200_OK # Or 400 if an explicit removal of non-assigned is an error
            )

        st_request.assistant = None
        st_request.assistant_date = None
        st_request.save(update_fields=['assistant', 'assistant_date'])

        return Response(
            {"message": f"Ассистент снят с заявки {st_request.RequestNumber}."},
            status=status.HTTP_200_OK
        )


#Nofoto - Поставить Без фото - Удалить из заявок
class NoFotoView(views.APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, barcode, *args, **kwargs): # barcode from URL
        if not is_senior_photographer(request.user):
            return Response(
                {"error": "Доступ запрещен. Только 'Старший фотограф' может выполнять это действие."},
                status=status.HTTP_403_FORBIDDEN
            )

        product = get_object_or_404(Product, barcode=barcode)

        # 1. Создаем Nofoto
        new_nofoto_entry = Nofoto.objects.create(product=product, user=request.user)

        # --- Проверка и отправка сообщения в Telegram ---
        nofotos_for_product = Nofoto.objects.filter(product=product).order_by('date')
        nofoto_count = nofotos_for_product.count()

        if nofoto_count >= 2:
            TELEGRAM_CHAT_ID = '-1002559221974'
            TELEGRAM_THREAD_ID = '305'

            product_seller_info = product.seller if product.seller is not None else "не указан"
            message_header = (
                f"Проставлено без фото более 2 раз для шк {product.barcode} - "
                f"{product.name} - магазин {product_seller_info}:"
            )
            
            message_lines = [message_header]
            for nofoto_item in nofotos_for_product:
                message_lines.append(nofoto_item.date.strftime('%d.%m.%Y'))
            
            full_message_text = "\n".join(message_lines)

            async_task(
                'telegram_bot.tasks.send_message_task',
                chat_id=TELEGRAM_CHAT_ID,
                text=full_message_text,
                message_thread_id=TELEGRAM_THREAD_ID
            )

        request_number_for_comment = None
        product_removed_from_request = False

        # 2. Ищем и удаляем товар из активной заявки
        st_request_product_item = STRequestProduct.objects.filter(
            product=product,
            request__status_id=3 # Только если заявка в статусе "На съемке"
        ).first()

        if st_request_product_item:
            st_request_for_comment = st_request_product_item.request
            request_number_for_comment = st_request_for_comment.RequestNumber
            st_request_product_item.delete()
            product_removed_from_request = True

        # 3. Создаем записи Product Operation
        try:
            operation_type_nofoto = ProductOperationTypes.objects.get(id=72)
            ProductOperation.objects.create(
                product=product,
                operation_type=operation_type_nofoto,
                user=request.user,
                comment=request_number_for_comment if request_number_for_comment else f"Товар {barcode} помечен как NoFoto"
            )

            operation_type_cannot_shoot = ProductOperationTypes.objects.get(id=56)
            ProductOperation.objects.create(
                product=product,
                operation_type=operation_type_cannot_shoot,
                user=request.user,
                comment="Не можем снять без вскрытия/забраковки"
            )
        except ProductOperationTypes.DoesNotExist as e:
            error_message = f"Тип операции не найден в ProductOperationTypes. ID, вызвавший ошибку: {e.args[0]}. Обратитесь к администратору."
            return Response({"error": error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- НАЧАЛО ИЗМЕНЕНИЯ: ДОБАВЛЕНА ПРОВЕРКА СТАТУСОВ ПРОДУКТА ---
        # Запись в Google Sheet будет произведена, только если все условия выполнены.
        should_write_to_sheet = (
            product.PhotoModerationStatus == 'Отклонено' and
            product.ProductModerationStatus in ['Отправлен на модерацию', 'Подтвержден', 'Подтверждён'] and
            product.SKUStatus in ['На модерации', 'Подтвержден', 'Подтверждён'] and
            product.ShopType == '3P'
        )

        if should_write_to_sheet:
            try:
                current_date_str = timezone.now().strftime('%d.%m.%Y')
                async_task(
                    'photographer.tasks.add_nofoto_to_google_sheet',
                    barcode=product.barcode,
                    name=product.name,
                    date_str=current_date_str,
                    task_name=f"Add-NoFoto-to-Sheet-{product.barcode}"
                )
            except Exception as e:
                # Логируем ошибку постановки задачи, но не останавливаем процесс
                print(f"Error scheduling Google Sheet task for barcode {product.barcode}: {e}")
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        message = f"Товар {barcode} помечен как 'Без фото'."
        if product_removed_from_request:
            message += f" Товар удален из активной заявки {request_number_for_comment}."
        
        return Response({"message": message}, status=status.HTTP_200_OK)

#Получение детальной информации об одной заявке STRequest
class STRequestDetailView(generics.RetrieveAPIView):
    """
    API эндпоинт для получения детальной информации о заявке STRequest.
    Доступен для любого аутентифицированного пользователя.
    """
    # queryset ensures we select_related/prefetch_related for efficiency
    queryset = STRequest.objects.all().select_related(
        'photographer', 'stockman', 'assistant', 'status'
    ).prefetch_related(
        'strequestproduct_set__product__category', # For Product.category
        'strequestproduct_set__photo_status',      # For STRequestProduct.photo_status
        'strequestproduct_set__sphoto_status'      # For STRequestProduct.sphoto_status
    )
    serializer_class = STRequestDetailSerializer
    permission_classes = [IsAuthenticated] # "Проверки на группу нет"
    lookup_field = 'RequestNumber'        # Field on STRequest model
    lookup_url_kwarg = 'request_number'   # Name of the argument in the URL pattern


#Изменить STRequestProduct.photo_status
class UpdateSTRequestProductPhotoStatusView(views.APIView):
    permission_classes = [IsAuthenticated] # Or specific permission if needed

    def post(self, request, *args, **kwargs):
        request_number = request.data.get('request_number')
        barcode = request.data.get('barcode')
        photo_status_id = request.data.get('photo_status_id')

        if not all([request_number, barcode, photo_status_id is not None]): # photo_status_id can be 0
            return Response(
                {"error": "Необходимо указать 'request_number', 'barcode' и 'photo_status_id'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            photo_status_id = int(photo_status_id)
        except ValueError:
            return Response({"error": "'photo_status_id' должен быть целым числом."}, status=status.HTTP_400_BAD_REQUEST)

        st_request_product = get_object_or_404(
            STRequestProduct,
            request__RequestNumber=request_number,
            product__barcode=barcode
        )
        new_photo_status = get_object_or_404(PhotoStatus, id=photo_status_id)

        st_request_product.photo_status = new_photo_status
        st_request_product.save(update_fields=['photo_status'])

        # --- ИЗМЕНЕНИЕ НАЧАЛО ---
        # Сериализуем обновленный объект и возвращаем его
        serializer = STRequestProductDetailSerializer(st_request_product)
        return Response(serializer.data, status=status.HTTP_200_OK)
        # --- ИЗМЕНЕНИЕ КОНЕЦ ---


#Изменить STRequestProduct.sphoto_status
class UpdateSTRequestProductSPhotoStatusView(views.APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        request_number = request.data.get('request_number')
        barcode = request.data.get('barcode')
        sphoto_status_id_str = request.data.get('sphoto_status_id')
        comment_from_request = request.data.get('comment') # Может быть None

        if not all([request_number, barcode, sphoto_status_id_str is not None]):
            return Response(
                {"error": "Необходимо указать 'request_number', 'barcode' и 'sphoto_status_id'."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            sphoto_status_id = int(sphoto_status_id_str)
        except ValueError:
            return Response({"error": "'sphoto_status_id' должен быть целым числом."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Обновляем select_related для включения всех необходимых полей
            st_request_product = get_object_or_404(
                STRequestProduct.objects.select_related(
                    'request', 
                    'request__photographer', 
                    'request__photographer__profile', # Если profile используется для telegram_id
                    'product', 
                    'sphoto_status',
                    'photo_status' 
                ),
                request__RequestNumber=request_number,
                product__barcode=barcode
            )
        except STRequestProduct.DoesNotExist: # get_object_or_404 сам выбросит Http404, но для ясности можно оставить
             return Response({"error": "Запись STRequestProduct не найдена."}, status=status.HTTP_404_NOT_FOUND)

        new_sphoto_status = get_object_or_404(SPhotoStatus, id=sphoto_status_id)

        # --- Основные обновления STRequestProduct ---
        st_request_product.sphoto_status = new_sphoto_status
        update_fields = ['sphoto_status']

        if comment_from_request is not None:
            st_request_product.comment = comment_from_request
            update_fields.append('comment')

        # --- Логика, зависящая от new_sphoto_status.id ---

        if new_sphoto_status.id == 1: # "Проверено СФ" или аналогичный статус

            allowed_photo_statuses = [1, 2, 25]
            # Проверяем, что photo_status существует и его id входит в разрешенный список
            if not st_request_product.photo_status or st_request_product.photo_status.id not in allowed_photo_statuses:
                current_status_name = st_request_product.photo_status.name if st_request_product.photo_status else "не установлен"
                return Response(
                    {"error": f"Невозможно установить статус 'Проверено'. Для проверки статус фото должен быть 'Готово', 'НТВ)' или 'БРАК'."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            st_request_product.senior_check_date = timezone.now()
            update_fields.append('senior_check_date')

            # Создание ProductOperation на основе photo_status
            current_photo_status = st_request_product.photo_status
            operation_type_id_for_po = None
            if current_photo_status:
                if current_photo_status.id == 1:
                    operation_type_id_for_po = 51
                elif current_photo_status.id == 2:
                    operation_type_id_for_po = 52
                elif current_photo_status.id == 25:
                    operation_type_id_for_po = 53
            
            if operation_type_id_for_po:
                try:
                    operation_type_instance = ProductOperationTypes.objects.get(id=operation_type_id_for_po)
                    photographer_user = st_request_product.request.photographer
                    
                    ProductOperation.objects.create(
                        product=st_request_product.product,
                        operation_type=operation_type_instance,
                        user=photographer_user, # Может быть None, если фотограф не назначен
                        comment=f"номер заявки {st_request_product.request.RequestNumber}"
                        # date создается автоматически
                    )
                except ProductOperationTypes.DoesNotExist:
                    # Критическая ошибка конфигурации, если тип операции не найден
                    return Response(
                        {"error": f"Тип операции ProductOperation с id={operation_type_id_for_po} не найден."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                except Exception as e: # Обработка других возможных ошибок при создании ProductOperation
                    # Логирование ошибки e
                    print(f"Error creating ProductOperation: {e}")
                    return Response(
                        {"error": "Ошибка при создании записи операции продукта."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            # else: # Если current_photo_status не None, но id не совпадает, или current_photo_status is None
                # Можно добавить логирование, если ProductOperation не создается, когда ожидалось

        elif new_sphoto_status.id == 2: # "На доработку" или аналогичный статус
            try:
                photo_status_to_set = PhotoStatus.objects.get(id=10)
                st_request_product.photo_status = photo_status_to_set
                update_fields.append('photo_status')
            except PhotoStatus.DoesNotExist:
                # Критическая ошибка конфигурации, если статус PhotoStatus с id=10 не найден
                return Response(
                    {"error": "Статус PhotoStatus с id=10 (для доработки) не найден."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Отправка сообщения в Telegram (существующая логика)
            photographer = st_request_product.request.photographer
            if photographer and hasattr(photographer, 'profile') and photographer.profile and photographer.profile.telegram_id:
                comment_for_tg = st_request_product.comment if st_request_product.comment else "Без комментария"
                message_text = (f"Правки по заявке {st_request_product.request.RequestNumber}:\n"
                                f"{st_request_product.product.barcode} - {comment_for_tg}")
                try:
                    async_task(
                        'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                        chat_id=photographer.profile.telegram_id,
                        text=message_text
                    )
                except Exception as e:
                    print(f"Failed to send Telegram message to {photographer.username} ({photographer.profile.telegram_id}): {e}")
            elif photographer:
                print(f"Photographer {photographer.username} has no telegram_id or profile for notification.")
            # else: # Фотограф не назначен на заявку
                # print(f"No photographer assigned to request {st_request_product.request.RequestNumber} for Telegram notification.")

        # Сохраняем все изменения в STRequestProduct
        try:
            st_request_product.save(update_fields=list(set(update_fields))) # Используем set для уникальности полей
        except IntegrityError as e:
            # Логирование ошибки e
            print(f"IntegrityError on STRequestProduct save: {e}")
            return Response({"error": "Ошибка сохранения данных, возможно, нарушена целостность."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Логирование ошибки e
            print(f"Generic error on STRequestProduct save: {e}")
            return Response({"error": "Неизвестная ошибка при сохранении данных."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # После всех манипуляций и сохранения, сериализуем финальное состояние объекта
        # и возвращаем его фронтенду.
        serializer = STRequestProductDetailSerializer(st_request_product)
        return Response(serializer.data, status=status.HTTP_200_OK)

#Вернуть заявку на съемку
class ReturnSTRequestToShootingView(APIView): # <<< Наследуемся от прямо импортированного APIView
    permission_classes = [IsAuthenticated]
    http_method_names = ['POST', 'options'] # <<< ЯВНО ДОБАВЬТЕ ЭТУ СТРОКУ

    def post(self, request, *args, **kwargs):
        print(f"--- ReturnSTRequestToShootingView POST HANDLER (v2) REACHED AT {datetime.now()} ---") # Добавьте отладочный print
        print(f"User: {request.user}, Is Senior: {is_senior_photographer(request.user)}")
        print(f"Request data: {request.data}")

        if not is_senior_photographer(request.user):
            return Response(
                {"error": "Доступ запрещен. Только 'Старший фотограф' может выполнять это действие."},
                status=status.HTTP_403_FORBIDDEN
            )

        request_number = request.data.get('request_number')
        if not request_number:
            return Response({"error": "Необходимо указать 'request_number'."}, status=status.HTTP_400_BAD_REQUEST)

        st_request = get_object_or_404(STRequest, RequestNumber=request_number)

        if not st_request.photo_date:
            return Response(
                {"error": f"Заявка {request_number} не была ранее назначена на съемку (отсутствует дата назначения фотографа 'photo_date')."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if timezone.now() - st_request.photo_date > timedelta(hours=24):
            return Response(
                {"error": (f"Невозможно вернуть заявку {request_number} на съемку. "
                           f"Прошло более 24 часов с момента назначения фотографа ({st_request.photo_date.strftime('%d.%m.%Y %H:%M')}).")},
                status=status.HTTP_400_BAD_REQUEST
            )

        target_status_id = 3
        try:
            target_status = STRequestStatus.objects.get(id=target_status_id)
        except STRequestStatus.DoesNotExist:
             return Response(
                {"error": f"Статус с ID {target_status_id} ('На съемке') не найден в системе."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if st_request.status_id == target_status_id:
             return Response(
                {"message": f"Заявка {request_number} уже находится в статусе '{target_status.name}'."},
                status=status.HTTP_200_OK
            )

        st_request.status = target_status
        st_request.save(update_fields=['status'])

        return Response(
            {"message": f"Заявка {request_number} возвращена на съемку (статус '{target_status.name}')."},
            status=status.HTTP_200_OK
        )


#Изменение ph_to_rt_comment
class UpdateSTRequestProductPhToRtCommentView(views.APIView):
    """
    Изменить поле ph_to_rt_comment в STRequestProduct.
    Ожидает POST с JSON:
    {
        "request_number": "REQ1234567890",
        "barcode": "0123456789012",
        "ph_to_rt_comment": "Ваш комментарий здесь"
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        request_number = request.data.get('request_number')
        barcode = request.data.get('barcode')
        comment = request.data.get('ph_to_rt_comment')

        if not all([request_number, barcode]) or comment is None:
            return Response(
                {"error": "Необходимо указать 'request_number', 'barcode' и 'ph_to_rt_comment'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Находим запись
        st_rp = get_object_or_404(
            STRequestProduct,
            request__RequestNumber=request_number,
            product__barcode=barcode
        )

        # Обновляем и сохраняем
        st_rp.ph_to_rt_comment = comment
        st_rp.save(update_fields=['ph_to_rt_comment'])

        # Возвращаем обновлённый объект
        serializer = STRequestProductDetailSerializer(st_rp)
        return Response(serializer.data, status=status.HTTP_200_OK)
