# guest/views.py

from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from django.db.models import Prefetch

from core.models import Product, STRequestProduct, STRequest
from .serializers import (
    CurrentProductSerializer,
    UserFullNameSerializer
    )
from .filters import ProductFilter
from .pagination import StandardResultsSetPagination

#Текущие товары на фс
class CurrentProductListView(generics.ListAPIView):
    """
    Возвращает список продуктов со статусом "В работе" (move_status_id=3),
    включая связанные номера заявок, сгруппированные по статусам.
    """
    serializer_class = CurrentProductSerializer
    permission_classes = [AllowAny]
    
    # Настройки фильтрации, сортировки и пагинации
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ProductFilter
    pagination_class = StandardResultsSetPagination
    
    # Поля и порядок сортировки по умолчанию
    ordering = ['income_date']
    ordering_fields = ['income_date', 'info', 'seller', 'priority', 'category_id']

    def get_queryset(self):
        """
        Формирует основной запрос.
        
        Ключевое исправление здесь - это Prefetch. Он эффективно подгружает
        ВСЕ связанные заявки для каждого продукта, не фильтруя их по статусу.
        Фильтрация по статусам (2, 3, 5) происходит позже, на уровне сериализатора,
        что и позволяет корректно заполнить все поля (STRequest2, STRequest3, STRequest5).
        """
        requests_prefetch = Prefetch(
            'strequestproduct_set',
            queryset=STRequestProduct.objects.select_related('request'),
            to_attr='requests_prefetch'
        )

        return Product.objects.filter(move_status_id=3).prefetch_related(requests_prefetch)

#Эндпоинт получения данных пользователя
class UserInfoDetailView(generics.RetrieveAPIView):
    queryset = User.objects.select_related('profile').all()
    serializer_class = UserFullNameSerializer
    permission_classes = [AllowAny] # Доступ без авторизации
    lookup_field = 'id'
