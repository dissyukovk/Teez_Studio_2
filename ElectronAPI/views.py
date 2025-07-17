#ElectronAPI/views.py
import os
from datetime import datetime, time, timedelta
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDay
from django.http import JsonResponse, FileResponse
from django.conf import settings
from rest_framework import status, permissions, generics
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .serializers import (
    STRequestSerializer,
    STRequestProductSerializer,
    STRequestPhotoTimeSerializer,
    ShootingDefectsSerializer
    )
from core.models import (
    STRequest,
    STRequestProduct,
    STRequestPhotoTime,
    ProductOperation,
    RetouchRequestProduct
    )


# --- Получение списка заявок на съемке ---
class PhotographerSTRequestsStatus3List(generics.ListAPIView):
    serializer_class = STRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return (
            STRequest.objects
            .filter(status__id=3, photographer=self.request.user)
            .order_by('-photo_date')
        )

# --- Детали заявки ---
class STRequestDetail(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, request_number):
        st_request = get_object_or_404(STRequest, RequestNumber=request_number)

        st_request_data = STRequestSerializer(st_request).data

        products_qs = STRequestProduct.objects.filter(request=st_request)
        products_data = STRequestProductSerializer(products_qs, many=True).data

        return Response({
            'request': st_request_data,
            'products': products_data
        })

# --- Начало съемки фотографом ---
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def shooting_start(request, request_number, barcode):
    # 1. Найти заявку по RequestNumber
    st_request = get_object_or_404(STRequest, RequestNumber=request_number)

    # 2. Найти связку заявка–товар по штрихкоду
    srp = get_object_or_404(
        STRequestProduct,
        request=st_request,
        product__barcode=barcode
    )

    # 3. Обновить статус фото и время начала съемки
    srp.photo_status_id = 10
    if not srp.shooting_time_start:
        srp.shooting_time_start = timezone.now()
    srp.save()

    # 4. Записать время начала съёмки (для истории)
    STRequestPhotoTime.objects.create(
        st_request_product=srp,
        photo_date=timezone.now(),
        user=request.user
    )

    # 5. Создать запись операции над продуктом (operation_type = 50)
    ProductOperation.objects.create(
        product=srp.product,
        operation_type_id=50,
        user=request.user
    )

    # 6. Отдать в ответ сам STRequestProduct
    serializer = STRequestProductSerializer(srp)
    return Response(serializer.data, status=status.HTTP_200_OK)

# --- Результаты съемки ---
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def shooting_results(request, request_number, barcode):
    st_request = get_object_or_404(STRequest, RequestNumber=request_number)
    srp = get_object_or_404(STRequestProduct, request=st_request, product__barcode=barcode)

    data = request.data
    srp.photo_status_id = data['photo_status']
    srp.photos_link      = data['photos_link']
    srp.ph_to_rt_comment = data.get('ph_to_rt_comment', '')
    
    srp.shooting_time_end = timezone.now()
    
    srp.save()

    return Response(STRequestProductSerializer(srp).data, status=status.HTTP_200_OK)

# --- Обновить photo_status ---
@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_photo_status(request, request_number, barcode):
    st_request = get_object_or_404(STRequest, RequestNumber=request_number)
    srp = get_object_or_404(STRequestProduct, request=st_request, product__barcode=barcode)

    srp.photo_status_id = request.data['photo_status']
    srp.save()

    return Response(STRequestProductSerializer(srp).data, status=status.HTTP_200_OK)

# --- обновить ph_to_ret_comment ---
@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_ph_to_rt_comment(request, request_number, barcode):
    """
    PATCH /api/ph_to_rt_comment/<request_number>/<barcode>/
    body: { "ph_to_rt_comment": "<new text or empty string>" }
    — Меняет только поле ph_to_rt_comment (может очищать).
    """
    st_request = get_object_or_404(STRequest, RequestNumber=request_number)
    srp = get_object_or_404(STRequestProduct, request=st_request, product__barcode=barcode)

    srp.ph_to_rt_comment = request.data.get('ph_to_rt_comment', '')
    srp.save()

    return Response(STRequestProductSerializer(srp).data, status=status.HTTP_200_OK)

# --- Получить Photo Times ---
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def photo_times_list(request, request_number):
    """
    GET /api/photo_times/<request_number>/
    Возвращает все записи STRequestPhotoTime для текущего пользователя за последние 3 дня.
    Параметр request_number игнорируется для обратной совместимости.
    """
    # 1. Определяем начальную дату для фильтрации (3 дня назад)
    three_days_ago = timezone.now() - timedelta(days=3)

    # 2. Выбираем все временные отметки для текущего пользователя за этот период.
    #    Фильтрация по 'request_number' больше не применяется.
    times_qs = STRequestPhotoTime.objects.filter(
        user=request.user,
        photo_date__gte=three_days_ago
    ).order_by('photo_date')

    # 3. Сериализуем и возвращаем данные (без изменений)
    serializer = STRequestPhotoTimeSerializer(times_qs, many=True)
    return Response(serializer.data)

# --- Браки по съемке ---
class ShootingDefectsList(generics.ListAPIView):
    serializer_class = ShootingDefectsSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None # Keep pagination disabled as we are manually slicing

    def get_queryset(self):
        # The original queryset
        queryset = (
            RetouchRequestProduct.objects
            .filter(
                retouch_status__id=3,
                sretouch_status__id=1,
                st_request_product__request__photographer=self.request.user
            )
            .select_related(
                'st_request_product__request',
                'st_request_product__product',
                'retouch_status'
            )
            .order_by('-id')
        )
        return queryset[:50]

# --- Статистика фотографа ---
class PhotographerStats(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, start_date_str, end_date_str):
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
        end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))

        queryset = STRequestProduct.objects.filter(
            request__photographer=request.user,
            request__photo_date__range=(start_datetime, end_datetime),
            photo_status__id__in=[1, 2, 25],
            sphoto_status__id=1
        )

        total_count = queryset.count()

        daily_counts = (
            queryset
            .annotate(day=TruncDay('request__photo_date'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        daily_data = {
            item['day'].strftime('%Y-%m-%d'): item['count'] for item in daily_counts
        }

        return Response({
            'total_count': total_count,
            'daily_counts': daily_data
        })


# --- ОБНОВЛЕНИЕ ПО ---
def update_server(request, version, platform):
    # This is a simplified example; you'll likely want to make this more robust
    latest_version = "1.0.0"  # You can store this in your database or a config file

    if version == latest_version:
        return JsonResponse({}, status=204)  # No content, a new version is not available

    # Path to your update files
    update_path = os.path.join(settings.MEDIA_ROOT, 'updates')
    exe_file = f'your-app-setup-{latest_version}.exe'
    nupkg_file = f'your-app-{latest_version}.nupkg'

    if platform == 'win32':
        # For Windows, you might need to serve both files or just the .exe
        # depending on your Electron update configuration
        return FileResponse(open(os.path.join(update_path, exe_file), 'rb'), filename=exe_file)

    # You can add logic for other platforms (e.g., 'darwin' for macOS) here

    return JsonResponse({'error': 'Platform not supported'}, status=404)

def latest_release(request):
    latest_version = "1.0.0"
    update_url = f"{settings.API_AND_MEDIA_BASE_URL}/media/updates/your-app-setup-{latest_version}.exe"
    return JsonResponse({
        "version": latest_version,
        "path": update_url
    })
