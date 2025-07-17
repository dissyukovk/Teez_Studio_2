from django.urls import path
from .views import (
    RetouchRequestListView,
    RetouchRequestDetailView,
    RetouchResultUpdateView,
    SendRequestForReviewView,
    DownloadRetouchRequestFilesView,
)

app_name = 'retoucher_api'

urlpatterns = [
    # - 1 - Эндпоинт для получения списка заявок по статусу
    # Пример: /api/retoucher/requests/1/
    path('requests/<int:status_id>/', RetouchRequestListView.as_view(), name='retouch-request-list'),

    # - 2 - Эндпоинт для получения деталей заявки по ее номеру
    # Пример: /api/retoucher/request/details/12345/
    path('request/details/<int:request_number>/', RetouchRequestDetailView.as_view(), name='retouch-request-detail'),

    # - 3 - Эндпоинт для обновления результата ретуши
    # Пример: PATCH /api/retoucher/result/update/
    path('result/update/', RetouchResultUpdateView.as_view(), name='retouch-result-update'),

    # - 4 - Эндпоинт для отправки заявки на проверку
    # Пример: POST /api/retoucher/request/send-for-review/5/  (где 5 - это PK заявки)
    path('request/send-for-review/<int:pk>/', SendRequestForReviewView.as_view(), name='send-request-for-review'),

     # - 5 - Эндпоинт для запуска скачивания файлов заявки на бэкенде
    # Пример: POST /api/retoucher/request/download-files/12345/
    path('request/download-files/<int:request_number>/', DownloadRetouchRequestFilesView.as_view(), name='download-retouch-request-files'),
]
