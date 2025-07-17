# guest/urls.py

from django.urls import path
from . import views

urlpatterns = [
    #Текущие товары на фс
    path('current-products/', views.CurrentProductListView.as_view(), name='current-product-list'),
    
    #Получение данных пользователя
    path('userinfo/<int:id>/', views.UserInfoDetailView.as_view(), name='user-info-detail'),
]
