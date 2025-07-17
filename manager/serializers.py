# serializers.py
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta

from core.models import (
    STRequest,
    STRequestProduct,
    ProductCategory,
    RetouchRequest,
    RetouchRequestProduct,
    )

#Сериализатор листа заявок на съемку
class STRequestSerializer(serializers.ModelSerializer):
    request_number = serializers.CharField(source='RequestNumber')
    status = serializers.CharField(source='status.name', default=None)
    stockman = serializers.SerializerMethodField()
    creation_date = serializers.SerializerMethodField()
    photographer = serializers.SerializerMethodField()
    photo_date = serializers.SerializerMethodField()
    total_products = serializers.IntegerField()
    count_priority = serializers.IntegerField()
    count_photo = serializers.IntegerField()
    count_checked = serializers.IntegerField()
    count_info = serializers.IntegerField()

    def get_stockman(self, obj):
        if obj.stockman:
            full_name = f"{obj.stockman.first_name} {obj.stockman.last_name}".strip()
            return full_name if full_name else None
        return None

    def get_photographer(self, obj):
        if obj.photographer:
            full_name = f"{obj.photographer.first_name} {obj.photographer.last_name}".strip()
            return full_name if full_name else None
        return None

    def format_date(self, dt):
        if not dt:
            return None
        # Приводим дату к локальному времени и форматируем
        local_dt = timezone.localtime(dt)
        return local_dt.strftime('%d.%m.%Y %H:%M:%S')

    def get_creation_date(self, obj):
        return self.format_date(obj.creation_date)

    def get_photo_date(self, obj):
        return self.format_date(obj.photo_date)

    class Meta:
        model = STRequest
        fields = [
            'request_number',
            'status',
            'stockman',
            'creation_date',
            'photographer',
            'photo_date',
            'total_products',
            'count_priority',
            'count_photo',
            'count_checked',
            'count_info'
        ]

# Сериализатор для категории товаров (id и name)
class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'reference_link', 'IsReference']

# Сериализатор для деталей товара в заявке
class STRequestProductDetailSerializer(serializers.ModelSerializer):
    barcode = serializers.CharField(source='product.barcode')
    name = serializers.CharField(source='product.name')
    category = ProductCategorySerializer(source='product.category', read_only=True)
    reference_link = serializers.CharField(source='product.category.reference_link', read_only=True)
    info = serializers.CharField(source='product.info', read_only=True)
    comment = serializers.CharField(read_only=True)
    priority = serializers.BooleanField(source='product.priority', read_only=True)
    photo_status = serializers.CharField(source='photo_status.name', read_only=True)
    sphoto_status = serializers.CharField(source='sphoto_status.name', read_only=True)
    photos_link = serializers.CharField(read_only=True)

    class Meta:
        model = STRequestProduct
        fields = [
            'barcode',
            'name',
            'category',
            'reference_link',
            'info',
            'comment',
            'priority',
            'photo_status',
            'sphoto_status',
            'photos_link'
        ]

# Сериализатор для деталей заявки на съемку
class STRequestDetailSerializer(serializers.ModelSerializer):
    request_number = serializers.CharField(source='RequestNumber')
    status = serializers.CharField(source='status.name', default=None)
    stockman = serializers.SerializerMethodField()
    creation_date = serializers.SerializerMethodField()
    photographer = serializers.SerializerMethodField()
    photo_date = serializers.SerializerMethodField()
    total_products = serializers.IntegerField()
    count_priority = serializers.IntegerField()
    count_photo = serializers.IntegerField()
    count_checked = serializers.IntegerField()
    count_info = serializers.IntegerField()
    products = STRequestProductDetailSerializer(source='strequestproduct_set', many=True, read_only=True)

    def get_stockman(self, obj):
        if obj.stockman:
            full_name = f"{obj.stockman.first_name} {obj.stockman.last_name}".strip()
            return full_name if full_name else None
        return None

    def get_photographer(self, obj):
        if obj.photographer:
            full_name = f"{obj.photographer.first_name} {obj.photographer.last_name}".strip()
            return full_name if full_name else None
        return None

    def format_date(self, dt):
        if not dt:
            return None
        local_dt = timezone.localtime(dt)
        return local_dt.strftime('%d.%m.%Y %H:%M:%S')

    def get_creation_date(self, obj):
        return self.format_date(obj.creation_date)

    def get_photo_date(self, obj):
        return self.format_date(obj.photo_date)

    class Meta:
        model = STRequest
        fields = [
            'request_number',
            'status',
            'stockman',
            'creation_date',
            'photographer',
            'photo_date',
            'total_products',
            'count_priority',
            'count_photo',
            'count_checked',
            'count_info',
            'products'
        ]

#сериалайзер листа заявок на ретушь
class RetouchRequestSerializer(serializers.ModelSerializer):
    request_number = serializers.CharField(source='RequestNumber')
    creation_date = serializers.DateTimeField(format="%d.%m.%Y %H:%M:%S")
    retouch_date = serializers.DateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    retoucher = serializers.SerializerMethodField()
    status = serializers.CharField(source='status.name')
    retouch_time = serializers.SerializerMethodField()
    products_count = serializers.IntegerField()
    priority_products_count = serializers.IntegerField()

    class Meta:
        model = RetouchRequest
        fields = (
            'request_number',
            'creation_date',
            'retoucher',
            'retouch_date',
            'status',
            'retouch_time',
            'products_count',
            'priority_products_count',
        )

    def get_retoucher(self, obj):
        if obj.retoucher:
            # Выводим в формате "FirstName LastName"
            return f"{obj.retoucher.first_name} {obj.retoucher.last_name}"
        return None

    def get_retouch_time(self, obj):
        if obj.creation_date and obj.retouch_date:
            delta = obj.retouch_date - obj.creation_date
            days = delta.days
            seconds = delta.seconds
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if days > 0:
                return f"{days} days, {hours:02}:{minutes:02}:{seconds:02}"
            else:
                return f"{hours:02}:{minutes:02}:{seconds:02}"
        return None

#детали заявки на ретушь - продукты
class RetouchRequestProductDetailSerializer(serializers.ModelSerializer):
    barcode = serializers.CharField(source='st_request_product.product.barcode')
    name = serializers.CharField(source='st_request_product.product.name')
    category = ProductCategorySerializer(source='st_request_product.product.category')
    reference_link = serializers.CharField(source='st_request_product.product.category.reference_link', allow_null=True)
    info = serializers.CharField(source='st_request_product.product.info', allow_null=True)
    priority = serializers.BooleanField(source='st_request_product.product.priority', read_only=True)
    retouch_status = serializers.CharField(source='retouch_status.name', allow_null=True)
    sretouch_status = serializers.CharField(source='sretouch_status.name', allow_null=True)
    retouch_link = serializers.CharField(allow_null=True)
    comment = serializers.CharField(allow_null=True)

    class Meta:
        model = RetouchRequestProduct
        fields = [
            'barcode',
            'name',
            'category',
            'reference_link',
            'info',
            'priority',
            'retouch_status',
            'sretouch_status',
            'retouch_link',
            'comment',
        ]

#детали заявки на ретушь
class RetouchRequestDetailSerializer(serializers.ModelSerializer):
    request_number = serializers.CharField(source='RequestNumber')
    creation_date = serializers.DateTimeField(format="%d.%m.%Y %H:%M:%S")
    retouch_date = serializers.DateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    retoucher = serializers.SerializerMethodField()
    status = serializers.CharField(source='status.name')
    retouch_time = serializers.SerializerMethodField()
    products_count = serializers.IntegerField()
    priority_products_count = serializers.IntegerField()
    products = RetouchRequestProductDetailSerializer(source='retouch_products', many=True)

    class Meta:
        model = RetouchRequest
        fields = [
            'request_number',
            'creation_date',
            'retoucher',
            'retouch_date',
            'status',
            'retouch_time',
            'products_count',
            'priority_products_count',
            'products',
        ]

    def get_retoucher(self, obj):
        if obj.retoucher:
            return f"{obj.retoucher.first_name} {obj.retoucher.last_name}"
        return None

    def get_retouch_time(self, obj):
        if obj.creation_date and obj.retouch_date:
            delta = obj.retouch_date - obj.creation_date
            days = delta.days
            seconds = delta.seconds
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if days > 0:
                return f"{days} days, {hours:02}:{minutes:02}:{seconds:02}"
            else:
                return f"{hours:02}:{minutes:02}:{seconds:02}"
        return None
