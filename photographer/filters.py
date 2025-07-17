import django_filters
from django.db.models import Q
from core.models import STRequest

class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    """
    Кастомный фильтр для поиска по вхождению в списке строк.
    Позволяет передавать несколько значений через запятую в query параметре.
    Например: ?request_numbers=123,456
    """
    pass


class STRequestFilter(django_filters.FilterSet):
    """
    Фильтр для STRequest с поддержкой множественных значений
    и поиска по вхождению ('icontains').
    """
    request_numbers = django_filters.CharFilter(method='filter_by_request_numbers', label="Request Numbers (comma-separated, contains)")
    barcodes = django_filters.CharFilter(method='filter_by_barcodes', label="Product Barcodes (comma-separated, contains)")

    class Meta:
        model = STRequest
        fields = []

    def filter_by_request_numbers(self, queryset, name, value):
        if not value:
            return queryset
        numbers = [num.strip() for num in value.split(',') if num.strip()]
        if not numbers:
            return queryset
        q_objects = Q()
        for number in numbers:
            q_objects |= Q(RequestNumber__icontains=number)
        return queryset.filter(q_objects)

    def filter_by_barcodes(self, queryset, name, value):
        if not value:
            return queryset
        barcodes_list = [bc.strip() for bc in value.split(',') if bc.strip()]
        if not barcodes_list:
            return queryset
        q_objects = Q()
        for barcode in barcodes_list:
            q_objects |= Q(strequestproduct__product__barcode__icontains=barcode)
        # distinct() важен при фильтрации по связанным моделям "многие-ко-многим"
        return queryset.filter(q_objects).distinct()
