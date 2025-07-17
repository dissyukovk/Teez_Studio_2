#ElectronAPI/serializers.py
from rest_framework import serializers, generics, permissions

from core.models import (
    STRequest,
    STRequestStatus,
    STRequestType,
    STRequestProduct,
    STRequestPhotoTime,
    Product,
    ProductCategory,
    PhotoStatus,
    SPhotoStatus,
    RetouchRequestProduct,
    RetouchStatus
)

class STRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = STRequestStatus
        fields = ('id', 'name')


class STRequestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = STRequestType
        fields = ('id', 'name')


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ('id', 'name', 'reference_link', 'IsReference')


class ProductSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer()

    class Meta:
        model = Product
        fields = (
            'id',
            'barcode',
            'name',
            'category',
            'info',
            'priority',
            'ProductID',
            'SKUID',
            'seller',
        )


class STRequestSimpleSerializer(serializers.ModelSerializer):
    """Минимальный сериалайзер для вложения в STRequestProductSerializer."""
    class Meta:
        model = STRequest
        fields = ('id', 'RequestNumber')


class PhotoStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoStatus
        fields = ('id', 'name')


class SPhotoStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SPhotoStatus
        fields = ('id', 'name')


class STRequestProductSerializer(serializers.ModelSerializer):
    request = STRequestSimpleSerializer()
    product = ProductSerializer()
    photo_status = PhotoStatusSerializer()
    sphoto_status = SPhotoStatusSerializer()

    class Meta:
        model = STRequestProduct
        fields = (
            'id',
            'request',
            'product',
            'photo_status',
            'sphoto_status',
            'comment',
            'OnRetouch',
            'shooting_time_start',
            'ph_to_rt_comment',
            'IsDeleteAccess',
            'photos_link'
        )


class STRequestSerializer(serializers.ModelSerializer):
    status = STRequestStatusSerializer()
    STRequestType = STRequestTypeSerializer()
    total_products = serializers.SerializerMethodField()
    not_shooted_products = serializers.SerializerMethodField()
    edit_products = serializers.SerializerMethodField()
    checked_products = serializers.SerializerMethodField()

    class Meta:
        model = STRequest
        fields = (
            'id',
            'RequestNumber',
            'status',
            'photo_date',
            'STRequestType',
            'total_products',
            'not_shooted_products',
            'edit_products',
            'checked_products',
        )

    def get_total_products(self, obj):
        return obj.strequestproduct_set.count()

    def get_not_shooted_products(self, obj):
        # photo_status not in {1,2,25}
        return obj.strequestproduct_set.exclude(photo_status__id__in=[1, 2, 25]).count()

    def get_edit_products(self, obj):
        # photo_status == 10 AND sphoto_status == 2
        return obj.strequestproduct_set.filter(photo_status__id=10, sphoto_status__id=2).count()

    def get_checked_products(self, obj):
        # sphoto_status == 1
        return obj.strequestproduct_set.filter(sphoto_status__id=1).count()


class STRequestPhotoTimeSerializer(serializers.ModelSerializer):
    st_request_product = STRequestProductSerializer(read_only=True)

    class Meta:
        model = STRequestPhotoTime
        fields = ('id', 'st_request_product', 'photo_date')

class RetouchStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetouchStatus
        fields = ('id', 'name')


class ShootingDefectsSerializer(serializers.ModelSerializer):
    st_request_product = STRequestProductSerializer()
    retouch_status = RetouchStatusSerializer()

    class Meta:
        model = RetouchRequestProduct
        fields = ('id', 'st_request_product', 'retouch_status', 'retouch_link', 'comment')
