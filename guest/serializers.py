# guest/serializer.py

from rest_framework import serializers
from django.contrib.auth.models import User
from core.models import (
    UserProfile,
    STRequest,
    STRequestStatus,
    STRequestProduct,
    STRequestType,
    Product,
    ProductCategory,
    ProductMoveStatus,
    PhotoStatus,
    SPhotoStatus,
    Nofoto,
    ProductOperationTypes,
    ProductOperation,
    RetouchRequest,
    RetouchRequestProduct,
    RetouchStatus,
    SRetouchStatus
)

class UserFullNameSerializer(serializers.ModelSerializer):
    """
    Сериализатор для пользователя, выводящий ID, полное имя (First Name + Last Name),
    группы и данные из UserProfile.
    """
    full_name = serializers.SerializerMethodField()
    # Получаем список названий групп, в которых состоит пользователь
    groups = serializers.StringRelatedField(many=True)

    # Получаем поля из связанной модели UserProfile
    # 'source' указывает, откуда брать данные. 'profile' - это related_name
    # из модели UserProfile к User.
    telegram_name = serializers.CharField(source='profile.telegram_name', read_only=True)
    telegram_id = serializers.CharField(source='profile.telegram_id', read_only=True)
    on_work = serializers.BooleanField(source='profile.on_work', read_only=True)
    phone_number = serializers.CharField(source='profile.phone_number', read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'full_name',
            'first_name',
            'last_name',
            'email',
            'groups',
            'telegram_name',
            'telegram_id',
            'on_work',
            'phone_number'
        )

    def get_full_name(self, obj):
        """
        Возвращает строку "Имя Фамилия".
        Обрабатывает случаи, когда имя или фамилия могут отсутствовать.
        """
        # Получаем имя и фамилию, заменяя None на пустую строку
        first = obj.first_name if obj.first_name else ""
        last = obj.last_name if obj.last_name else ""

        # Соединяем части и удаляем лишние пробелы по краям
        full_name = f"{first} {last}".strip()

        # Если имя и фамилия не заданы, возвращаем username как запасной вариант
        return full_name if full_name else obj.username

class STRequestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = STRequestType
        fields = ('id', 'name')

class STRequestStatusSerializer(serializers.ModelSerializer):
    """
    Сериализатор для статуса заявки.
    """
    class Meta:
        model = STRequestStatus
        fields = ('id', 'name')

class STRequestListSerializer(serializers.ModelSerializer):
    photographer = UserFullNameSerializer(read_only=True)
    stockman = UserFullNameSerializer(read_only=True)
    assistant = UserFullNameSerializer(read_only=True)
    status = STRequestStatusSerializer(read_only=True)
    STRequestType = STRequestTypeSerializer(read_only=True)

    # Кастомные поля, значения которых берутся из аннотаций в View
    total_products = serializers.IntegerField(source='total_products_count', read_only=True)
    priority = serializers.BooleanField(source='has_priority_product', read_only=True)
    info = serializers.BooleanField(source='has_product_with_info', read_only=True)

    for_check_count = serializers.IntegerField(source='for_check_count_annotation', read_only=True)

    class Meta:
        model = STRequest
        fields = (
            'id',
            'RequestNumber',
            'photographer',
            'stockman',
            'creation_date',
            'status',
            'photo_date',
            'photo_date_end',
            'photo_time',
            'assistant',
            'assistant_date',
            'check_time',
            'total_products',
            'priority',
            'info',
            'for_check_count',
            'STRequestType',
            'STRequestTypeBlocked'
        )
        read_only_fields = fields # Все поля только для чтения

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ('id', 'name', 'reference_link', 'IsBlocked', 'IsReference', 'STRequestType', 'IsDeleteAccess')

class PhotoStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoStatus
        fields = ('id', 'name')

class SPhotoStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SPhotoStatus
        fields = ('id', 'name')

class ProductMoveStatusSeriallizer(serializers.ModelSerializer):
    class Meta:
        model = ProductMoveStatus
        fields = ('id', 'name')

class ProductSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)
    move_status = ProductMoveStatusSeriallizer(read_only=True)
    income_stockman = UserFullNameSerializer(read_only=True)
    outcome_stockman = UserFullNameSerializer(read_only=True)

    class Meta:
        model = Product
        fields = (
            'barcode',
            'name',
            'cell',
            'seller',
            'move_status',
            'info',
            'priority',
            'category',
            'income_date',
            'outcome_date',
            'income_stockman',
            'outcome_stockman',
            'ProductID',
            'SKUID',
            'ShopType',
            'ShopName',
            'ProductStatus',
            'ProductModerationStatus',
            'PhotoModerationStatus',
            'SKUStatus'
        )

#Product - текущие
class CurrentProductSerializer(ProductSerializer):
    """
    Extends the base ProductSerializer to include related STRequest numbers,
    filtered by status.
    """
    STRequest2 = serializers.SerializerMethodField()
    STRequest3 = serializers.SerializerMethodField()
    STRequest5 = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        # Inherit fields from the parent and add the new ones
        fields = ProductSerializer.Meta.fields + ('STRequest2', 'STRequest3', 'STRequest5')

    def _get_requests_by_status(self, obj, status_id):
        """Helper method to filter prefetched requests by status."""
        if not hasattr(obj, 'requests_prefetch'):
            return []
        
        return [
            rp.request.RequestNumber
            for rp in obj.requests_prefetch
            if rp.request and rp.request.status_id == status_id
        ]

    def get_STRequest2(self, obj):
        """Returns a list of RequestNumbers for requests with status=2."""
        return self._get_requests_by_status(obj, 2)

    def get_STRequest3(self, obj):
        """Returns a list of RequestNumbers for requests with status=3."""
        return self._get_requests_by_status(obj, 3)

    def get_STRequest5(self, obj):
        """Returns a list of RequestNumbers for requests with status=5."""
        return self._get_requests_by_status(obj, 5)

class STRequestProductDetailSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    photo_status = PhotoStatusSerializer(read_only=True, allow_null=True)
    sphoto_status = SPhotoStatusSerializer(read_only=True, allow_null=True)

    class Meta:
        model = STRequestProduct
        fields = (
            'id',
            'product',
            'photo_status',
            'sphoto_status',
            'photos_link',
            'comment',
            'OnRetouch',
            'IsDeleteAccess',
            'ph_to_rt_comment',
            'shooting_time_start',
            'shooting_time_end',
            'shooting_duration',
            'senior_check_date'
        )

class STRequestDetailSerializer(STRequestListSerializer):
    # Inherits fields and methods from STRequestListSerializer
    # The related name from STRequest to STRequestProduct is 'strequestproduct_set' by default
    products = STRequestProductDetailSerializer(many=True, read_only=True, source='strequestproduct_set')

    class Meta(STRequestListSerializer.Meta): # Inherit Meta from parent
        # Add 'products' to the list of fields
        fields = STRequestListSerializer.Meta.fields + ('products',)
        read_only_fields = fields # All fields are read-only as per parent

class RetouchStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetouchStatus
        fields = ('id', 'name')

class SRetouchStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SRetouchStatus
        fields = ('id', 'name')

class RetouchRequestProductSerializer(serializers.ModelSerializer):
    st_request_product = STRequestProductDetailSerializer(read_only=True)
    retouch_status = RetouchStatusSerializer(read_only=True)
    sretouch_status = SRetouchStatusSerializer(read_only=True)

    class Meta:
        model = RetouchRequestProduct
        fields = (
            'id',
            'st_request_product',
            'retouch_status',
            'sretouch_status',
            'retouch_link',
            'comment',
            'retouch_end_date',
            'IsOnUpload',
        )

class RetouchRequestSerializer(serializers.ModelSerializer):
    retoucher = UserFullNameSerializer(read_only=True)
    status = RetouchStatusSerializer(read_only=True)
    retouch_products = RetouchRequestProductSerializer(many=True, read_only=True)

    class Meta:
        model = RetouchRequest
        fields = (
            'id',
            'RequestNumber',
            'retoucher',
            'creation_date',
            'retouch_date',
            'status',
            'comments',
            'download_task_id',
            'download_started_at',
            'download_completed_at',
            'download_error',
            'retouch_products',
        )
