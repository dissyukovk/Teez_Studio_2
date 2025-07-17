# guest/filters.py

import django_filters
from django.db.models import Q
from datetime import timedelta

from core.models import Product

class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    """
    Helper filter for comma-separated character values (e.g., seller, category).
    """
    pass

class ProductFilter(django_filters.FilterSet):
    """
    Custom filter set for the Product model.
    """
    # Filter for multiple barcodes, finding partial matches from the start
    barcode = django_filters.CharFilter(method='filter_barcode', label="Barcode (comma-separated)")

    # Case-insensitive search for product name
    name = django_filters.CharFilter(lookup_expr='icontains')

    # Filter for multiple exact seller IDs
    seller = CharInFilter(field_name='seller', lookup_expr='in')

    # Filter for products where the 'info' field is not empty
    info = django_filters.BooleanFilter(method='filter_info')
    
    # Standard boolean filter for priority
    priority = django_filters.BooleanFilter()

    # Filter for multiple exact category IDs
    category_id = CharInFilter(field_name='category_id', lookup_expr='in')
    
    # Date range filters for income_date
    income_date_after = django_filters.DateFilter(field_name='income_date', lookup_expr='gte', label='Income Date From (YYYY-MM-DD)')
    income_date_before = django_filters.DateFilter(method='filter_income_date_before', label='Income Date To (YYYY-MM-DD)')

    class Meta:
        model = Product
        fields = ['barcode', 'name', 'seller', 'info', 'priority', 'category_id']

    def filter_barcode(self, queryset, name, value):
        """
        Custom filter for barcodes. Handles comma-separated values
        and finds any barcode that starts with one of the provided values.
        """
        barcodes = [b.strip() for b in value.split(',') if b.strip()]
        if not barcodes:
            return queryset
        
        # Create a Q object for each barcode to use OR condition
        query = Q()
        for barcode in barcodes:
            query |= Q(barcode__startswith=barcode)
        
        return queryset.filter(query)

    def filter_info(self, queryset, name, value):
        """
        Filters for products that have meaningful info.
        - If True, returns products where info is not null and not empty.
        - If False, returns products where info is null or empty.
        """
        if value:
            return queryset.filter(info__isnull=False).exclude(info__exact='')
        return queryset.filter(Q(info__isnull=True) | Q(info__exact=''))

    def filter_income_date_before(self, queryset, name, value):
        """
        Includes the entire 'end date' in the range by filtering up to the start of the next day.
        """
        end_of_day = value + timedelta(days=1)
        return queryset.filter(income_date__lt=end_of_day)
