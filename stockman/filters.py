import django_filters
from django_filters import rest_framework as filters
from datetime import timedelta
from django.db.models import Q
from core.models import STRequest, Invoice, InvoiceProduct, Product

class STRequestFilter(django_filters.FilterSet):
    # Фильтр по номерам заявок (массив номеров через запятую)
    request_numbers = django_filters.CharFilter(method='filter_request_numbers')
    # Фильтр по штрихкодам через связь с STRequestProduct
    barcodes = django_filters.CharFilter(method='filter_barcodes')
    # Фильтры по дате создания (формат дд.мм.гггг)
    creation_date_from = django_filters.DateFilter(
        field_name='creation_date', lookup_expr='gte', input_formats=['%d.%m.%Y']
    )
    creation_date_to = django_filters.DateFilter(
        method='filter_creation_date_to', input_formats=['%d.%m.%Y']
    )
    # Фильтр по статусам (массив id через запятую)
    statuses = django_filters.CharFilter(method='filter_statuses')
    # Фильтр по товароведу (stockman) – массив id через запятую
    stockman = django_filters.CharFilter(method='filter_stockman')
    # Фильтр по фотографу – массив id через запятую
    photographer = django_filters.CharFilter(method='filter_photographer')
    # Фильтры по дате фото (формат дд.мм.гггг)
    photo_date_from = django_filters.DateFilter(
        field_name='photo_date', lookup_expr='gte', input_formats=['%d.%m.%Y']
    )
    photo_date_to = django_filters.DateFilter(
        method='filter_photo_date_to', input_formats=['%d.%m.%Y']
    )
    
    def filter_creation_date_to(self, queryset, name, value):
        # Добавляем один день, чтобы включить конечную дату
        next_day = value + timedelta(days=1)
        return queryset.filter(creation_date__lt=next_day)
    
    def filter_photo_date_to(self, queryset, name, value):
        next_day = value + timedelta(days=1)
        return queryset.filter(photo_date__lt=next_day)
    
    def filter_request_numbers(self, queryset, name, value):
        numbers = [v.strip() for v in value.split(',') if v.strip()]
        if numbers:
            query = Q()
            for num in numbers:
                query |= Q(RequestNumber__icontains=num)
            queryset = queryset.filter(query)
        return queryset

    def filter_barcodes(self, queryset, name, value):
        codes = [v.strip() for v in value.split(',') if v.strip()]
        if codes:
            queryset = queryset.filter(strequestproduct__product__barcode__in=codes).distinct()
        return queryset

    def filter_statuses(self, queryset, name, value):
        status_ids = [v.strip() for v in value.split(',') if v.strip()]
        if status_ids:
            queryset = queryset.filter(status__id__in=status_ids)
        return queryset

    def filter_stockman(self, queryset, name, value):
        stockman_ids = [v.strip() for v in value.split(',') if v.strip()]
        if stockman_ids:
            queryset = queryset.filter(stockman__id__in=stockman_ids)
        return queryset

    def filter_photographer(self, queryset, name, value):
        photographer_ids = [v.strip() for v in value.split(',') if v.strip()]
        if photographer_ids:
            queryset = queryset.filter(photographer__id__in=photographer_ids)
        return queryset

    class Meta:
        model = STRequest
        fields = []

class InvoiceFilter(filters.FilterSet):
    invoice_numbers = filters.CharFilter(method='filter_invoice_numbers')
    barcodes = filters.CharFilter(method='filter_barcodes')

    class Meta:
        model = Invoice
        fields = []

    def filter_invoice_numbers(self, queryset, name, value):
        numbers = value.split(',')
        q = Q()
        for num in numbers:
            num = num.strip()
            if num:
                q |= Q(InvoiceNumber__contains=num)
        return queryset.filter(q)

    def filter_barcodes(self, queryset, name, value):
        barcodes = value.split(',')
        # Фильтрация через связь: invoiceproduct__product__barcode
        return queryset.filter(invoiceproduct__product__barcode__in=barcodes).distinct()

class CurrentNumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass

class CurrentCharInFilter(filters.BaseInFilter, filters.CharFilter):
    pass

class CurrentProductFilter(filters.FilterSet):
    barcode = CurrentCharInFilter(field_name='barcode', lookup_expr='in')
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    seller = CurrentNumberInFilter(field_name='seller', lookup_expr='in')
    category_id = CurrentNumberInFilter(field_name='category__id', lookup_expr='in')
    income_date_from = filters.DateFilter(field_name='income_date', lookup_expr='gte', input_formats=['%d.%m.%Y'])
    income_date_to = filters.DateFilter(field_name='income_date', lookup_expr='lte', input_formats=['%d.%m.%Y'])
    info_present = filters.BooleanFilter(method='filter_info')
    priority = filters.BooleanFilter(field_name='priority')

    def filter_info(self, queryset, name, value):
        if value:
            return queryset.exclude(info__isnull=True).exclude(info__exact='')
        return queryset

    class Meta:
        model = Product
        fields = ['barcode', 'name', 'seller', 'category_id', 'income_date_from', 'income_date_to', 'info_present', 'priority']
