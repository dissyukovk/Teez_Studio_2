import django_filters
from django_filters import DateFilter, FilterSet, BaseInFilter, NumberFilter, CharFilter
from core.models import STRequestProduct, ProductOperation, ProductOperationTypes

class SRReadyProductFilter(django_filters.FilterSet):
    barcode = django_filters.CharFilter(field_name='product__barcode', lookup_expr='icontains')
    name = django_filters.CharFilter(field_name='product__name', lookup_expr='icontains')
    OnRetouch = django_filters.BooleanFilter(field_name='OnRetouch')
    priority = django_filters.BooleanFilter(field_name='product__priority')
    photo_date = django_filters.DateTimeFromToRangeFilter(field_name='request__photo_date')
    # Добавляем фильтр по статусу. Допустим, статус лежит в STRequest, связанной через request
    # Если статус - ForeignKey, можно фильтровать по ID: status_id
    # Или, если статус - CharField, по имени.
    status = django_filters.NumberFilter(field_name='request__status_id')  # пример, если статус - числовой id

    class Meta:
        model = STRequestProduct
        fields = ['barcode', 'name', 'OnRetouch', 'priority', 'photo_date', 'status']

class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass

class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    pass

class ProductOperationFilter(FilterSet):
    barcode = CharInFilter(field_name='product__barcode', lookup_expr='in')
    seller = NumberInFilter(field_name='product__seller', lookup_expr='in')
    # ВАЖНО: именно NumberInFilter, а не NumberFilter
    operation_type = NumberInFilter(field_name='operation_type__id', lookup_expr='in')

    date_from = DateFilter(field_name='date', lookup_expr='gte')
    date_to = DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model = ProductOperation
        fields = ['barcode', 'seller', 'operation_type', 'date_from', 'date_to']
