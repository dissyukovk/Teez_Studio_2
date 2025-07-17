from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
import django_filters

from .models import (
    Product,
    Render,
    RetouchStatus,
    SeniorRetouchStatus,
    ModerationUpload,
    UploadStatus,
    RejectedReason,
    StudioRejectedReason,
    ModerationStudioUpload,
    RenderCheckResult
    )


class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    """
    Кастомный фильтр для поиска по списку строковых значений,
    переданных в виде строки через запятую.
    Например: ?field=value1,value2,value3
    """
    pass

class RenderFilter(django_filters.FilterSet):
    """
    Определяет набор фильтров для модели Render.
    """
    # Создаем фильтр для поля Barcode связанной модели Product.
    # field_name='Product__Barcode' - указывает на поле для фильтрации.
    # lookup_expr='in' - указывает, что нужно использовать SQL-оператор IN.
    Product__Barcode = CharInFilter(field_name='Product__Barcode', lookup_expr='in')

    class Meta:
        model = Render
        # Перечисляем все поля, по которым будет возможна фильтрация.
        fields = ['IsSuitable', 'RetouchStatus__id', 'Retoucher__id', 'Product__Barcode']
