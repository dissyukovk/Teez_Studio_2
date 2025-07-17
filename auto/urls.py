# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('delete_empty_requests/', views.DeleteEmptyRequestsView.as_view(), name='delete_empty_requests'),
    path('update_stuck_requests/', views.UpdateStuckRequestsView.as_view(), name='update_stuck_requests'),
    path('userprofile_by_telegram/', views.userprofile_by_telegram, name='userprofile_by_telegram'),
    path('verify_credentials/', views.verify_credentials, name='verify_credentials'),
    path('update_telegram_id/', views.update_telegram_id, name='update_telegram_id'),
    path('order-status-refresh/', views.order_status_refresh, name='order_status_refresh'),
    #роставить чек тайм, удалить потом
    path('strequests/update-check-time/', views.update_strequest_check_time_directly, name='update_strequest_check_time_directly'),
    #Ручной запуск скрипта IsOnOrder
    path('trigger-update-order-status/', views.trigger_update_order_status_task, name='trigger_update_order_status_task'),
]
