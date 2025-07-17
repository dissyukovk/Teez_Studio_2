from django.urls import path
from . import views

urlpatterns = [
    path('orders/', views.OrderListView.as_view(), name='order-list'),
    path('order-statuses/', views.OrderStatusListView.as_view(), name='order-status-list'),
    path('order-detail/<int:order_number>/', views.OrderDetailAPIView.as_view(), name='order-detail'),
    path('order-start-assembly/<int:order_number>/', views.OrderStartAssemblyView.as_view(), name='order_start_assembly'),

    #Статистика заказов
    path('order-stats/', views.OrderStatsView.as_view(), name='order-stats'),
]
