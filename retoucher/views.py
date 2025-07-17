# Retoucher/views
import os
import tempfile
import zipfile
import io
import logging
import re
from django_q.tasks import async_task

from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from core.models import RetouchRequest, RetouchRequestProduct, UserProfile, RetouchStatus
from .permissions import IsRetoucher
from .serializers import RetouchRequestSerializer, RetouchRequestProductSerializer
from .pagination import StandardResultsSetPagination
from .tasks import download_retouch_request_files_task

logger = logging.getLogger(__name__)

# - 1 -
class RetouchRequestListView(generics.ListAPIView):
    """
    Получение списка Retouch Request для текущего пользователя (ретушера)
    с фильтрацией по статусу из URL.
    """
    serializer_class = RetouchRequestSerializer
    permission_classes = [IsAuthenticated, IsRetoucher]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        Этот метод фильтрует заявки, чтобы вернуть только те, которые
        назначены текущему пользователю и имеют указанный статус.
        """
        user = self.request.user
        status_id = self.kwargs.get('status_id')
        
        return RetouchRequest.objects.filter(
            retoucher=user, 
            status_id=status_id
        ).select_related('retoucher', 'status').prefetch_related('retouch_products')

# - 2 -
class RetouchRequestDetailView(generics.ListAPIView):
    """
    Получение детальной информации о продуктах в конкретной Retouch Request
    по ее номеру (RequestNumber).
    """
    serializer_class = RetouchRequestProductSerializer
    permission_classes = [IsAuthenticated, IsRetoucher]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        Возвращает список продуктов для заявки с указанным RequestNumber,
        проверяя, что заявка принадлежит текущему пользователю.
        """
        request_number = self.kwargs.get('request_number')
        # Сначала получаем заявку, чтобы убедиться, что она принадлежит ретушеру
        retouch_request = get_object_or_404(
            RetouchRequest, 
            RequestNumber=request_number, 
            retoucher=self.request.user
        )
        # Затем возвращаем связанные продукты
        return RetouchRequestProduct.objects.filter(
            retouch_request=retouch_request
        ).select_related(
            'retouch_request', 
            'st_request_product__product__category', 
            'retouch_status', 
            'sretouch_status'
        )

# - 3 -
class RetouchResultUpdateView(views.APIView):
    """
    Обновление статуса и ссылки на ретушь для конкретного продукта в заявке.
    Принимает id продукта в заявке (RetouchRequestProduct), id статуса и ссылку.
    """
    permission_classes = [IsAuthenticated, IsRetoucher]

    def patch(self, request, *args, **kwargs):
        product_id = request.data.get('retouch_request_product_id')
        status_id = request.data.get('retouch_status_id')
        retouch_link = request.data.get('retouch_link')

        if not product_id or not status_id:
            return Response(
                {"error": "retouch_request_product_id and retouch_status_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем, что статус 'Готово к проверке' (id=2) требует наличия ссылки
        if int(status_id) == 2 and not retouch_link:
            return Response(
                {"error": "retouch_link is required for status 'Готово к проверке'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Находим продукт и проверяем, что он принадлежит заявке текущего пользователя
            product_to_update = RetouchRequestProduct.objects.get(
                id=product_id, 
                retouch_request__retoucher=request.user
            )
        except RetouchRequestProduct.DoesNotExist:
            return Response(
                {"error": "Product not found or you do not have permission to edit it."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Обновляем поля
        product_to_update.retouch_status_id = status_id
        if retouch_link is not None:
             product_to_update.retouch_link = retouch_link
        
        product_to_update.save(update_fields=['retouch_status', 'retouch_link'])

        serializer = RetouchRequestProductSerializer(product_to_update)
        return Response(serializer.data, status=status.HTTP_200_OK)


# - 4 -
class SendRequestForReviewView(views.APIView):
    """
    Отправка заявки на ретушь на проверку старшему ретушеру.
    Меняет статус заявки на 'На проверке' (id=3) и рассылает уведомления.
    """
    permission_classes = [IsAuthenticated, IsRetoucher]

    def post(self, request, pk, *args, **kwargs):
        try:
            # Находим заявку по pk и проверяем, что она принадлежит текущему пользователю
            retouch_request = RetouchRequest.objects.get(pk=pk, retoucher=request.user)
        except RetouchRequest.DoesNotExist:
            return Response(
                {"error": "Request not found or you do not have permission to send it for review."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Обновляем статус и дату
        retouch_request.status_id = 3  # 'На проверке'
        retouch_request.retouch_date = timezone.now()
        retouch_request.save(update_fields=['status', 'retouch_date'])

        # Отправка уведомлений старшим ретушерам
        senior_retouchers = User.objects.filter(
            groups__name='Старший ретушер',
            profile__on_work=True
        )

        user_full_name = f"{request.user.first_name} {request.user.last_name}".strip()
        message = (f"Заявка {retouch_request.RequestNumber} отправлена на проверку.\n"
                   f"Ретушер - {user_full_name}")

        for senior in senior_retouchers:
            if hasattr(senior, 'profile') and senior.profile.telegram_id:
                async_task(
                    'telegram_bot.tasks.send_message_task',
                    chat_id=senior.profile.telegram_id,
                    text=message
                )

        serializer = RetouchRequestSerializer(retouch_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

# - 5 - НОВЫЙ ЭНДПОИНТ для запуска скачивания на бэкенде
class DownloadRetouchRequestFilesView(APIView):
    """
    Эндпоинт для ручного запроса ZIP: если нет — запускает новую задачу,
    если в процессе — возвращает 202, если уже готов — отдает ссылку.
    """
    permission_classes = [IsAuthenticated, IsRetoucher]

    def post(self, request, request_number, *args, **kwargs):
        # Получаем заявку и проверяем доступ
        ret_req = get_object_or_404(
            RetouchRequest,
            RequestNumber=request_number,
            retoucher=request.user
        )

        # Путь к финальному ZIP
        final_dir = os.path.join(settings.MEDIA_ROOT, 'retouch_downloads')
        final_name = f"Исходники_{request_number}.zip"
        final_path = os.path.join(final_dir, final_name)
        download_url = f"{settings.API_AND_MEDIA_BASE_URL}{settings.MEDIA_URL}retouch_downloads/{final_name}"

        # 1) Если файл на диске уже есть — считаем, что он готов
        if os.path.exists(final_path):
            # Если вдруг метка в БД не стоит (например, архив был создан вручную) — проставим её
            if not ret_req.download_completed_at:
                RetouchRequest.objects.filter(pk=ret_req.pk).update(
                    download_completed_at=timezone.now(),
                    download_task_id=None
                )

            # Отдаём сразу ссылку и НЕ запускаем новую таску
            return Response(
                {
                    "message": "Архив уже готов.",
                    "download_url": download_url
                },
                status=status.HTTP_200_OK
            )

        # 2) Архив в процессе сборки
        if ret_req.download_task_id and not ret_req.download_completed_at:
            logger.info(f"[Download] Архив для заявки {request_number} всё ещё генерируется (task_id={ret_req.download_task_id}).")
            return Response(
                {"message": "Генерация архива в процессе."},
                status=status.HTTP_202_ACCEPTED
            )

        # 3) Запускаем новую задачу
        task_id = async_task(
            'retoucher.tasks.download_retouch_request_files_task',
            ret_req.id,
            request.user.id
        )
        ret_req.download_task_id    = task_id
        ret_req.download_started_at = timezone.now()
        ret_req.save(update_fields=['download_task_id', 'download_started_at'])

        logger.info(f"[Download] Запущена ZIP-задача {task_id} для заявки {request_number}.")
        return Response(
            {"message": "Задача запущена, ждите уведомления.", "task_id": task_id},
            status=status.HTTP_202_ACCEPTED
        )
    
