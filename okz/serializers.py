from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.fields import DateTimeField
from core.models import (
    Order,
    OrderStatus,
    OrderProduct,
    Product,
    ProductMoveStatus,
    STRequest,
    STRequestStatus,
    STRequestProduct,
    PhotoStatus,
    SPhotoStatus,
    Invoice,
    InvoiceProduct
    )

class TimeZonePreservingDateTimeField(DateTimeField):
    def to_representation(self, value):
        if not value:
            return None
        # Если формат указан, просто форматируем дату без вызова localtime()
        local_value = timezone.localtime(value)
        if self.format:
            return local_value.strftime(self.format)
        return value

class OrderSerializer(serializers.ModelSerializer):
    order_number = serializers.IntegerField(source='OrderNumber')
    creation_date = TimeZonePreservingDateTimeField(source="date", format="%d.%m.%Y %H:%M:%S", allow_null=True)
    creator = serializers.SerializerMethodField()
    status_id = serializers.IntegerField(source='status.id')
    status_name = serializers.CharField(source='status.name')
    assembly_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    assembly_user = serializers.SerializerMethodField()
    accept_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    accept_date_end = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    acceptance_time = serializers.SerializerMethodField()
    accept_user = serializers.SerializerMethodField()
    total_products = serializers.SerializerMethodField()
    priority_products = serializers.SerializerMethodField()
    accepted_products = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'order_number',
            'creation_date',
            'creator',
            'status_id',
            'status_name',
            'assembly_date',
            'assembly_user',
            'accept_date',
            'accept_date_end',
            'acceptance_time',
            'accept_user',
            'total_products',
            'priority_products',
            'accepted_products'
        )
    
    def get_creator(self, obj):
        if obj.creator:
            full_name = f"{obj.creator.first_name} {obj.creator.last_name}".strip()
            return full_name if full_name else None
        return None

    def get_assembly_user(self, obj):
        if obj.assembly_user:
            full_name = f"{obj.assembly_user.first_name} {obj.assembly_user.last_name}".strip()
            return full_name if full_name else None
        return None

    def get_accept_user(self, obj):
        if obj.accept_user:
            full_name = f"{obj.accept_user.first_name} {obj.accept_user.last_name}".strip()
            return full_name if full_name else None
        return None

    def get_acceptance_time(self, obj):
        if obj.accept_date and obj.accept_date_end:
            diff = obj.accept_date_end - obj.accept_date
            total_seconds = int(diff.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        return None

    def get_total_products(self, obj):
        return obj.orderproduct_set.count()

    def get_priority_products(self, obj):
        return obj.orderproduct_set.filter(product__priority=True).count()

    def get_accepted_products(self, obj):
        return obj.orderproduct_set.filter(accepted=True).count()


class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatus
        fields = ('id', 'name')


class OrderProductSerializer(serializers.ModelSerializer):
    barcode = serializers.CharField(source='product.barcode')
    name = serializers.CharField(source='product.name')
    cell = serializers.CharField(source='product.cell')
    seller = serializers.IntegerField(source='product.seller', allow_null=True)
    product_move_status_name = serializers.CharField(source='product.move_status.name', default=None)
    product_move_status_id = serializers.IntegerField(source='product.move_status.id', default=None)
    accepted_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)

    class Meta:
        model = OrderProduct
        fields = [
            "barcode",
            "name",
            "cell",
            "seller",
            "product_move_status_name",
            "product_move_status_id",
            "accepted",
            "accepted_date",
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    order_number = serializers.IntegerField(source='OrderNumber')
    order_status = serializers.SerializerMethodField()
    creator = serializers.SerializerMethodField()
    assembly_user = serializers.SerializerMethodField()
    accept_user = serializers.SerializerMethodField()
    assembly_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    accept_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    accept_date_end = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    accept_time = serializers.SerializerMethodField()
    total_products = serializers.SerializerMethodField()
    priority_products = serializers.SerializerMethodField()
    accepted_products = serializers.SerializerMethodField()
    date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    products = OrderProductSerializer(source='orderproduct_set', many=True)

    def get_order_status(self, obj):
        if obj.status:
            return {"id": obj.status.id, "name": obj.status.name}
        return None

    def get_creator(self, obj):
        if obj.creator:
            return f"{obj.creator.first_name} {obj.creator.last_name}"
        return None

    def get_assembly_user(self, obj):
        if obj.assembly_user:
            return f"{obj.assembly_user.first_name} {obj.assembly_user.last_name}"
        return None

    def get_accept_user(self, obj):
        if obj.accept_user:
            return f"{obj.accept_user.first_name} {obj.accept_user.last_name}"
        return None

    def get_accept_time(self, obj):
        if obj.accept_date and obj.accept_date_end:
            delta = obj.accept_date_end - obj.accept_date
            total_seconds = int(delta.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return None

    def get_total_products(self, obj):
        return obj.orderproduct_set.count()

    def get_priority_products(self, obj):
        return obj.orderproduct_set.filter(product__priority=True).count()

    def get_accepted_products(self, obj):
        return obj.orderproduct_set.filter(accepted=True).count()

    class Meta:
        model = Order
        fields = [
            "order_number",
            "date",
            "order_status",
            "creator",
            "assembly_user",
            "assembly_date",
            "accept_user",
            "accept_date",
            "accept_date_end",
            "accept_time",
            "total_products",
            "priority_products",
            "accepted_products",
            "products",
        ]
