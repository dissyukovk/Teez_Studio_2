from django.urls import path
from . import views

urlpatterns = [
    path('create-order-check-barcodes/', views.CreateOrderCheckBarcodes.as_view(), name='create_order_check_barcodes'),
    path('create-order-end/', views.CreateOrderEnd.as_view(), name='create_order_end'),
    path('manager-bulk-upload/', views.manager_bulk_upload, name='manager_bulk_upload'),
    path('fsallstats/', views.FSAllstats, name='fsallstats'),
    path('photographers_statistic/', views.PhotographersStatistic.as_view(), name='photographers_statistic'),
    path('queues/', views.get_current_queues, name='current_queues'),
    path('strequest-list/', views.STRequestListView.as_view(), name='strequest-list'),
    path('strequest-detail/<str:requestnumber>/', views.STRequestDetailView.as_view(), name='strequest-detail'),
    path('retouchrequestlist/', views.RetouchRequestList.as_view(), name='retouchrequestlist'),
    path('RetouchRequestDetail/<RequestNumber>/', views.RetouchRequestDetail.as_view(), name='retouchrequestdetail'),
    path('product-operations-stats/', views.ProductOperationStatsView.as_view(), name='product-operations-stats'),
    path('update_info_tgbot/', views.update_info_tgbot, name='tgbot_update_product_info'),

    #среднее время хранения на фс
    path('average-processing-time/', views.AverageProcessingTimeView.as_view(), name='average_processing_time'),

    #Проверка ШК
    path('barcode-check/', views.BarcodeCheckView.as_view(), name='barcode_check'),

    #Проверка ШК Новая
    path('barcode-check-sequential/', views.BarcodeSequentialCheckView.as_view(), name='barcode_check_sequential'),

    #Среднее время съемки
    path('average-shooting-time/', views.AverageShootingTimeView.as_view(), name='average_shooting_time'),

    #Дэшборд по приемке и заказам
    path('acceptance-dashboard/', views.AcceptanceDashboardView.as_view(), name='acceptance_dashboard'),
]
