from rest_framework import serializers
from django.contrib.auth.models import User # Импортируем стандартную модель User
from core.models import (
    STRequest,
    STRequestStatus,
    STRequestProduct,
    STRequestType,
    Product,
    ProductCategory, # Added
    PhotoStatus,     # Added
    SPhotoStatus,    # Added
    Nofoto,          # Added
    ProductOperationTypes, # Added
    ProductOperation
    )

class UserFullNameSerializer(serializers.ModelSerializer):
    """
    Сериализатор для пользователя, выводящий ID и полное имя (First Name + Last Name).
    """
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'full_name') # Выводим ID и кастомное поле full_name

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
    """
    Сериализатор для списка STRequest с кастомными полями и форматированием.
    """
    # Формат вывода даты и времени
    DATETIME_FORMAT = '%d.%m.%Y %H:%M:%S'

    # Используем новый сериализатор для пользователей
    photographer = UserFullNameSerializer(read_only=True)
    stockman = UserFullNameSerializer(read_only=True)
    assistant = UserFullNameSerializer(read_only=True)
    status = STRequestStatusSerializer(read_only=True)
    STRequestType = STRequestTypeSerializer(read_only=True)

    # Задаем формат вывода для полей даты и времени
    # input_formats указываем для полноты, хотя здесь поля read_only
    creation_date = serializers.DateTimeField(format=DATETIME_FORMAT, read_only=True, input_formats=['iso-8601'])
    photo_date = serializers.DateTimeField(format=DATETIME_FORMAT, read_only=True, input_formats=['iso-8601'])
    assistant_date = serializers.DateTimeField(format=DATETIME_FORMAT, read_only=True, input_formats=['iso-8601'])

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
            'creation_date',  # Будет отформатировано
            'status',
            'photo_date',     # Будет отформатировано
            'assistant',
            'assistant_date', # Будет отформатировано
            'total_products',
            'priority',
            'info',
            'for_check_count',
            'STRequestType'
        )
        read_only_fields = fields # Все поля только для чтения

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ('id', 'name', 'reference_link', 'IsReference')

class PhotoStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoStatus
        fields = ('id', 'name')

class SPhotoStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SPhotoStatus
        fields = ('id', 'name')

class ProductDetailForSTRequestSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)
    class Meta:
        model = Product
        fields = ('barcode', 'name', 'seller', 'info', 'priority', 'category', 'income_date', 'ProductID', 'SKUID')

class STRequestProductDetailSerializer(serializers.ModelSerializer):
    product = ProductDetailForSTRequestSerializer(read_only=True)
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
        )

class STRequestDetailSerializer(STRequestListSerializer):
    # Inherits fields and methods from STRequestListSerializer
    # The related name from STRequest to STRequestProduct is 'strequestproduct_set' by default
    products = STRequestProductDetailSerializer(many=True, read_only=True, source='strequestproduct_set')

    class Meta(STRequestListSerializer.Meta): # Inherit Meta from parent
        # Add 'products' to the list of fields
        fields = STRequestListSerializer.Meta.fields + ('products',)
        read_only_fields = fields # All fields are read-only as per parent
