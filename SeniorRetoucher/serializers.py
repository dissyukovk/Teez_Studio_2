#SeniorRetoucher.serializers
from rest_framework import serializers
from django.contrib.auth.models import User, Group
from core.models import (
    ProductCategory,
    Product,
    STRequest,
    STRequestProduct,
    STRequestStatus,
    RetouchRequest,
    RetouchRequestStatus,
    RetouchRequestProduct,
    RetouchStatus,
    SRetouchStatus,
    PhotoStatus,
    SPhotoStatus,
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

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'reference_link', 'IsReference']

class ProductSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            'barcode', 
            'name', 
            'priority', 
            'info', 
            'ProductID', 
            'SKUID', 
            'seller',
            'category' # Добавляем сюда вложенный сериализатор категории
        ]

class STRequestProductSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = STRequestProduct
        fields = [
            'id', 
            'photos_link', 
            'ph_to_rt_comment',
            'product',
            'request'
        ]

class RetouchRequestStatusSerializer(serializers.ModelSerializer):
    """
    Сериализатор для статуса заявки на ретушь.
    """
    class Meta:
        model = RetouchRequestStatus
        fields = ('id', 'name')


class RetouchRequestSerializer(serializers.ModelSerializer):
    """
    Сериализатор для заявки на ретушь с вложенной информацией.
    """
    retoucher = UserFullNameSerializer(read_only=True)
    status = RetouchRequestStatusSerializer(read_only=True)
    total_products = serializers.SerializerMethodField()
    unchecked_product = serializers.SerializerMethodField()

    class Meta:
        model = RetouchRequest
        fields = (
            'id',
            'RequestNumber',
            'retoucher',
            'creation_date',
            'retouch_date',
            'status',
            'total_products',
            'unchecked_product',
        )

    def get_total_products(self, obj):
        """
        Возвращает общее количество связанных продуктов в заявке на ретушь.
        """
        return obj.retouch_products.count()

    def get_unchecked_product(self, obj):
        """
        Возвращает количество продуктов, у которых статус ретуши 'Готово к проверке' (ID=2),
        а статус проверки старшим ретушером не является 'Проверено' (ID=1).
        """
        return obj.retouch_products.filter(retouch_status_id=2).exclude(sretouch_status_id=1).count()

class RetouchStatusSerializer(serializers.ModelSerializer):
    """
    Сериализатор для статуса ретуши продукта.
    """
    class Meta:
        model = RetouchStatus
        fields = ('id', 'name')

class SRetouchStatusSerializer(serializers.ModelSerializer):
    """
    Сериализатор для статуса проверки ретуши старшим ретушером.
    """
    class Meta:
        model = SRetouchStatus
        fields = ('id', 'name')

class RetouchRequestProductSerializer(serializers.ModelSerializer):
    """
    Сериализатор для продукта в заявке на ретушь со всей вложенной информацией.
    """
    retouch_request = RetouchRequestSerializer(read_only=True)
    st_request_product = STRequestProductSerializer(read_only=True)
    retouch_status = RetouchStatusSerializer(read_only=True)
    sretouch_status = SRetouchStatusSerializer(read_only=True)

    class Meta:
        model = RetouchRequestProduct
        fields = [
            'id',
            'retouch_request',
            'st_request_product',
            'retouch_status',
            'sretouch_status',
            'retouch_link',
            'comment',
            'IsOnUpload',
        ]
