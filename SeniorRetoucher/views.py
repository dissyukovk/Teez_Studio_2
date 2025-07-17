# SeniorRetoucher.views
import logging
import datetime
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q, Max
from django.contrib.auth.models import User, Group
from django_q.tasks import async_task
from aiogram.utils.markdown import hbold
from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .pagination import StandardResultsSetPagination
from .permissions import IsSeniorRetoucher

from core.models import (
    STRequestProduct,
    ProductOperation,
    RetouchRequest,
    RetouchRequestProduct,
    UserProfile,
    RetouchRequestStatus
)

from .serializers import (
    STRequestProductSerializer,
    RetouchRequestSerializer,
    RetouchRequestProductSerializer,
    UserFullNameSerializer,
)

logger = logging.getLogger(__name__)

# Existing view
class ReadyForRetouchListView(generics.ListAPIView):
    serializer_class = STRequestProductSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]

    def get_queryset(self):
        queryset = STRequestProduct.objects.filter(
            photo_status_id=1,
            sphoto_status_id=1,
            OnRetouch=False
        ).select_related(
            'product', 
            'product__category'
        )

        barcodes_param = self.request.query_params.get('barcodes')
        if barcodes_param:
            barcodes_list = [barcode.strip() for barcode in barcodes_param.split(',') if barcode.strip()]
            if barcodes_list:
                queryset = queryset.filter(product__barcode__in=barcodes_list)

        return queryset.order_by('-product__priority', 'product__income_date')

# - 0 - Permission check is handled by `permission_classes` in each view.

# - 1 - Get 'on work' retouchers
class RetouchersOnWorkListView(generics.ListAPIView):
    """
    Returns a list of users from the 'Ретушер' group who are marked as 'on_work'.
    """
    serializer_class = UserFullNameSerializer
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]

    def get_queryset(self):
        return User.objects.filter(
            groups__name='Ретушер',
            profile__on_work=True
        ).order_by('first_name', 'last_name')

# - 2 - Create RetouchRequest with a retoucher
class CreateRetouchRequestView(views.APIView):
    """
    Creates a new RetouchRequest, assigns it to a retoucher, and links STRequestProducts.
    """
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        st_request_product_ids = request.data.get('st_request_product_ids')
        retoucher_id = request.data.get('retoucher_id')

        if not st_request_product_ids or not retoucher_id:
            return Response(
                {"error": "st_request_product_ids and retoucher_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            retoucher = User.objects.get(id=retoucher_id)
            st_products = STRequestProduct.objects.filter(id__in=st_request_product_ids, OnRetouch=False)

            if len(st_products) != len(st_request_product_ids):
                return Response({"error": "One or more products are already on retouch or do not exist."}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response({"error": "Retoucher not found."}, status=status.HTTP_404_NOT_FOUND)
            
        # --- ИЗМЕНЕННЫЙ БЛОК ---
        # Генерация инкрементального номера заявки.
        # Находим максимальный существующий номер.
        last_request_number = RetouchRequest.objects.aggregate(max_number=Max('RequestNumber'))['max_number']
        
        # Если в таблице есть записи, прибавляем 1, иначе начинаем с 1 (или любого другого числа).
        if last_request_number is not None:
            new_request_number = last_request_number + 1
        else:
            new_request_number = 1 # Первая заявка будет с номером 1
        # --- КОНЕЦ ИЗМЕНЕННОГО БЛОКА ---

        # Create RetouchRequest
        new_request = RetouchRequest.objects.create(
            RequestNumber=new_request_number, # Используем новый сгенерированный номер
            retoucher=retoucher,
            status_id=2  # "В работе"
        )

        # Create links and update statuses
        products_to_link = []
        for st_product in st_products:
            products_to_link.append(
                RetouchRequestProduct(
                    retouch_request=new_request,
                    st_request_product=st_product
                )
            )
            # Create ProductOperation
            ProductOperation.objects.create(
                product=st_product.product,
                operation_type_id=6, # "Назначено на ретушь"
                user=retoucher
            )
        
        RetouchRequestProduct.objects.bulk_create(products_to_link)
        st_products.update(OnRetouch=True)

        # ——— СCHEDULE ZIP TASK ———
        def _schedule_download():
            task_id = async_task(
                'retoucher.tasks.download_retouch_request_files_task',
                new_request.id,
                retoucher.id
            )
            # обновляем поля в отдельной транзакции
            RetouchRequest.objects.filter(pk=new_request.id).update(
                download_task_id=task_id,
                download_started_at=timezone.now()
            )
            logger.info(f"[Create] Scheduled ZIP task {task_id} for RetouchRequest {new_request.id}")

        transaction.on_commit(_schedule_download)

        # Send Telegram notification
        try:
            if retoucher.profile and retoucher.profile.telegram_id:
                message = (f"Вам назначена заявка {new_request.RequestNumber}, "
                           f"количество SKU: {len(products_to_link)}")
                async_task(
                    'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                    chat_id=retoucher.profile.telegram_id,
                    text=message
                )
        except Exception as e:
            # Log the error but don't fail the request
            print(f"Failed to send Telegram message to {retoucher.username}: {e}")

        serializer = RetouchRequestSerializer(new_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# - 3 - List RetouchRequests
class RetouchRequestListView(generics.ListAPIView):
    """
    Lists RetouchRequests with filtering and sorting options.
    """
    serializer_class = RetouchRequestSerializer
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = RetouchRequest.objects.all().select_related('retoucher', 'status').prefetch_related('retouch_products')
        
        # Filter by status from URL
        status_id = self.kwargs.get('status_id')
        if status_id:
            queryset = queryset.filter(status_id=status_id)

        # Filter by RequestNumber
        request_number = self.request.query_params.get('RequestNumber')
        if request_number:
            queryset = queryset.filter(RequestNumber=request_number)

        # Filter by barcodes
        barcodes_param = self.request.query_params.get('barcodes')
        if barcodes_param:
            barcodes_list = [barcode.strip() for barcode in barcodes_param.split(',') if barcode.strip()]
            if barcodes_list:
                queryset = queryset.filter(retouch_products__st_request_product__product__barcode__in=barcodes_list).distinct()
        
        # Filter by date
        retouch_date_str = self.request.query_params.get('retouch_date')
        if retouch_date_str:
            try:
                retouch_date = datetime.datetime.strptime(retouch_date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(retouch_date__date=retouch_date)
            except ValueError:
                # Ignore invalid date format
                pass

        return queryset.order_by('-creation_date')

# - 4 - Get RetouchRequest details by RequestNumber
class RetouchRequestDetailView(generics.ListAPIView):
    """
    Retrieves all products associated with a single RetouchRequest by its RequestNumber.
    """
    serializer_class = RetouchRequestProductSerializer
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        request_number = self.kwargs.get('request_number')
        return RetouchRequestProduct.objects.filter(
            retouch_request__RequestNumber=request_number
        ).select_related(
            'retouch_request',
            'st_request_product__product__category',
            'retouch_status',
            'sretouch_status'
        ).order_by('id')

# - 5 - Change Retouch Status
class UpdateRetouchStatusView(views.APIView):
    """
    Updates the retouch_status of a specific RetouchRequestProduct.
    """
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]

    def patch(self, request, *args, **kwargs):
        product_id = request.data.get('retouch_request_product_id')
        status_id = request.data.get('status_id')

        if not product_id or status_id is None:
            return Response({"error": "retouch_request_product_id and status_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = RetouchRequestProduct.objects.get(id=product_id)
            product.retouch_status_id = status_id
            product.save()
            serializer = RetouchRequestProductSerializer(product)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except RetouchRequestProduct.DoesNotExist:
            return Response({"error": "Product not found in any retouch request."}, status=status.HTTP_404_NOT_FOUND)

# - 6 - Change SRetouch Status
class UpdateSRetouchStatusView(views.APIView):
    """
    Updates the sretouch_status and optionally the comment of a specific RetouchRequestProduct.
    Sets retouch_end_date if the new status is 'Проверено' (ID=1).
    Also creates a ProductOperation based on the retouch_status.
    """
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]
    
    def patch(self, request, *args, **kwargs):
        product_id = request.data.get('retouch_request_product_id')
        status_id = request.data.get('status_id')
        comment = request.data.get('comment')

        if not product_id or status_id is None:
            return Response(
                {"error": "retouch_request_product_id and status_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = RetouchRequestProduct.objects.get(id=product_id)
            product.sretouch_status_id = status_id
            
            if comment is not None:
                product.comment = comment

            # Если статус "Проверено" (ID=1), выполняем дополнительную логику
            if int(status_id) == 1:
                product.retouch_end_date = timezone.now()

                # --- НОВЫЙ БЛОК: Создание ProductOperation ---
                operation_type_mapping = {
                    2: 62,
                    3: 63,
                    4: 64,
                    5: 65,
                    7: 67,
                }
                
                # Безопасно получаем ID статуса ретуши
                current_retouch_status_id = product.retouch_status.id if product.retouch_status else None
                
                # Находим соответствующий тип операции
                operation_type_id = operation_type_mapping.get(current_retouch_status_id)
                
                # Если тип операции найден, создаем запись
                if operation_type_id:
                    try:
                        ProductOperation.objects.create(
                            product=product.st_request_product.product,
                            operation_type_id=operation_type_id,
                            user=product.retouch_request.retoucher,
                            comment=product.retouch_link
                        )
                    except Exception as e:
                        # Логируем ошибку, но не прерываем основной процесс
                        print(f"Could not create ProductOperation for RetouchRequestProduct {product.id}: {e}")
                # --- КОНЕЦ НОВОГО БЛОКА ---

            product.save()
            serializer = RetouchRequestProductSerializer(product)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except RetouchRequestProduct.DoesNotExist:
            return Response({"error": "Product not found in any retouch request."}, status=status.HTTP_404_NOT_FOUND)

# - 7 - Change RetouchRequest Status
class UpdateRetouchRequestStatusView(views.APIView):
    """
    Updates the status of a RetouchRequest to 'На доработку' (4) or 'Завершено' (5).
    """
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]

    def patch(self, request, request_number, status_id, *args, **kwargs):
        allowed_statuses = [4, 5]
        if status_id not in allowed_statuses:
            return Response({"error": f"Status can only be changed to {allowed_statuses}."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            retouch_request = RetouchRequest.objects.get(RequestNumber=request_number)
        except RetouchRequest.DoesNotExist:
            return Response({"error": "RetouchRequest not found."}, status=status.HTTP_404_NOT_FOUND)

        if status_id == 4: # На доработку
            retouch_request.status_id = 4
            retouch_request.save()
            # Send Telegram notification
            retoucher = retouch_request.retoucher
            try:
                if retoucher and retoucher.profile and retoucher.profile.telegram_id:
                    message = f"Правки по заявке {retouch_request.RequestNumber}"
                    async_task(
                        'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                        chat_id=retoucher.profile.telegram_id,
                        text=message
                    )
            except Exception as e:
                print(f"Failed to send Telegram message for corrections to {retoucher.username}: {e}")

        elif status_id == 5: # Завершено
            # Check if all products are verified
            total_products = retouch_request.retouch_products.count()
            verified_products = retouch_request.retouch_products.filter(sretouch_status_id=1).count()

            if total_products != verified_products:
                return Response({"error": "Not all products have been verified (sretouch_status_id=1)."}, status=status.HTTP_400_BAD_REQUEST)
            
            retouch_request.status_id = 5
            retouch_request.retouch_date = timezone.now()
            retouch_request.save()
        
        serializer = RetouchRequestSerializer(retouch_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

# - 8 - Statistics
class RetoucherStatisticsView(views.APIView):
    """
    Provides daily statistics on completed and verified retouches per retoucher.
    """
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]

    def get(self, request, *args, **kwargs):
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({"error": "Date parameter is required (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Find retouchers who had requests completed on the target date
        stats = User.objects.filter(
            retouch_requests__status_id=5,
            retouch_requests__retouch_date__date=target_date
        ).annotate(
            # Count products that were 'Готово к проверке' and 'Проверено' within those completed requests
            checked_products_count=Count(
                'retouch_requests__retouch_products',
                filter=Q(
                    retouch_requests__retouch_products__retouch_status_id=2, # Готово к проверке
                    retouch_requests__retouch_products__sretouch_status_id=1  # Проверено
                )
            )
        ).filter(checked_products_count__gt=0).order_by('first_name')

        # Format the response
        result = []
        for user in stats:
            user_data = UserFullNameSerializer(user).data
            user_data['completed_and_checked_products'] = user.checked_products_count
            result.append(user_data)

        return Response(result, status=status.HTTP_200_OK)

# - 9 - переназначение ретушера
class ReassignRetoucherView(views.APIView):
    """
    Переназначает RetouchRequest новому ретушеру, отправляет уведомление,
    обновляет статус заявки и продуктов, а также создает записи в истории операций.
    """
    permission_classes = [IsAuthenticated, IsSeniorRetoucher]

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        request_number = request.data.get('request_number')
        new_retoucher_id = request.data.get('retoucher_id')

        if not request_number or not new_retoucher_id:
            return Response(
                {"error": "request_number and retoucher_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            retouch_request = RetouchRequest.objects.get(RequestNumber=request_number)
        except RetouchRequest.DoesNotExist:
            return Response({"error": "RetouchRequest not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            new_retoucher = User.objects.get(id=new_retoucher_id)
        except User.DoesNotExist:
            return Response({"error": "New retoucher not found."}, status=status.HTTP_404_NOT_FOUND)

        # --- НОВЫЙ БЛОК ЛОГИКИ ---
        # 1. Обновляем ретушера и статус заявки
        retouch_request.retoucher = new_retoucher
        retouch_request.status_id = 2  # Статус "В работе"
        retouch_request.save()

        # 2. Очищаем статусы проверки для всех продуктов в заявке
        retouch_request.retouch_products.update(sretouch_status=None, comment=None, retouch_end_date=None)

        # 3. Создаем новые записи ProductOperation для каждого продукта
        operations_to_create = []
        # Оптимизируем запрос, чтобы сразу получить связанные продукты
        products_in_request = retouch_request.retouch_products.select_related(
            'st_request_product__product'
        ).all()

        for rp in products_in_request:
            if rp.st_request_product and rp.st_request_product.product:
                operations_to_create.append(
                    ProductOperation(
                        product=rp.st_request_product.product,
                        operation_type_id=6,  # "Назначено на ретушь"
                        user=new_retoucher
                    )
                )
        
        if operations_to_create:
            ProductOperation.objects.bulk_create(operations_to_create)
        # --- КОНЕЦ НОВОГО БЛОКА ---

        # Отправляем уведомление в Telegram новому ретушеру
        try:
            if new_retoucher.profile and new_retoucher.profile.telegram_id:
                num_products = retouch_request.retouch_products.count()
                message = (f"Вам назначена заявка {retouch_request.RequestNumber}, "
                           f"количество SKU: {num_products}")
                async_task(
                    'telegram_bot.tasks.send_message_task',
                    chat_id=new_retoucher.profile.telegram_id,
                    text=message
                )
        except Exception as e:
            # Логируем ошибку, но не прерываем запрос
            logger.error(f"Failed to send Telegram message to new retoucher {new_retoucher.username}: {e}")

        serializer = RetouchRequestSerializer(retouch_request)
        return Response(serializer.data, status=status.HTTP_200_OK)
