from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Count
from .models import Product, STRequestProduct, STRequest, Invoice, InvoiceProduct, ProductMoveStatus, ProductOperation, Order, OrderStatus, OrderProduct, ProductCategory, RetouchStatus, STRequestStatus, ProductOperationTypes, UserURLs, STRequestHistory, STRequestHistoryOperations, Nofoto

class UserSerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'groups']

    def get_groups(self, obj):
        return [group.name for group in obj.groups.all()]

class ProductSerializer(serializers.ModelSerializer):
    move_status_id = serializers.IntegerField(source='move_status.id', allow_null=True, default=None)
    move_status = serializers.CharField(source='move_status.name', default='N/A')
    request_number = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()
    income_stockman = serializers.SerializerMethodField()
    outcome_stockman = serializers.SerializerMethodField()
    photographer = serializers.SerializerMethodField()
    retoucher = serializers.SerializerMethodField()
    request_status = serializers.SerializerMethodField()
    photos_link = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', default='N/A')  # Прямой доступ через связь
    category_id = serializers.IntegerField(source='category.id', default='N/A')  # Прямой доступ через связь
    category_reference_link = serializers.CharField(source='category.reference_link', default='N/A')  # Ссылка категории
    
    def get_request_number(self, obj):
        # Use preloaded related data
        request_product = obj.strequestproduct_set.first()
        if request_product and request_product.request:
            return request_product.request.RequestNumber
        return 'N/A'

    def get_invoice_number(self, obj):
        # Use preloaded related data
        invoice_product = obj.invoiceproduct_set.first()
        if invoice_product and invoice_product.invoice:
            return invoice_product.invoice.InvoiceNumber
        return 'N/A'

    def get_income_stockman(self, obj):
        if obj.income_stockman:
            return f"{obj.income_stockman.first_name} {obj.income_stockman.last_name}"
        return 'N/A'

    def get_outcome_stockman(self, obj):
        if obj.outcome_stockman:
            return f"{obj.outcome_stockman.first_name} {obj.outcome_stockman.last_name}"
        return 'N/A'

    def get_photographer(self, obj):
        request_product = obj.strequestproduct_set.first()  # Правильное использование related manager
        if request_product and request_product.request and request_product.request.photographer:
            return f"{request_product.request.photographer.first_name} {request_product.request.photographer.last_name}"
        return 'N/A'

    def get_retoucher(self, obj):
        request_product = obj.strequestproduct_set.first()  # Правильное использование related manager
        if request_product and request_product.request and request_product.request.retoucher:
            return f"{request_product.request.retoucher.first_name} {request_product.request.retoucher.last_name}"
        return 'N/A'

    def get_request_status(self, obj):
        request_product = obj.strequestproduct_set.first()  # Правильное использование related manager
        if request_product and request_product.request and request_product.request.status:
            return request_product.request.status.name
        return 'N/A'

    def get_photos_link(self, obj):
        request_product = obj.strequestproduct_set.first()  # Правильное использование related manager
        if request_product and request_product.request and request_product.request.photos_link:
            return request_product.request.photos_link
        return 'N/A'

    class Meta:
        model = Product
        fields = ['barcode', 'name', 'category_id', 'category_name', 'category_reference_link', 'seller', 'income_date', 'outcome_date', 
                  'income_stockman', 'outcome_stockman', 'in_stock_sum', 'cell', 'request_number', 
                  'invoice_number', 'move_status_id', 'move_status', 'photographer', 'retoucher', 'request_status', 
                  'photos_link', 'retouch_link']

class STRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = STRequestStatus
        fields = ['id', 'name']  # Включаем id и название статуса

class STRequestSerializer(serializers.ModelSerializer):
    total_products = serializers.SerializerMethodField()
    photographer_first_name = serializers.CharField(source="photographer.first_name", default="Не назначен")
    photographer_last_name = serializers.CharField(source="photographer.last_name", default="")
    retoucher_first_name = serializers.CharField(source="retoucher.first_name", default="Не назначен")
    retoucher_last_name = serializers.CharField(source="retoucher.last_name", default="")
    sr_comment = serializers.CharField(allow_blank=True, required=False)
    stockman = UserSerializer()
    status = STRequestStatusSerializer()

    class Meta:
        model = STRequest
        fields = [
            'RequestNumber',
            'creation_date',
            'photographer',
            'retoucher',
            'stockman',
            'status',
            'total_products',
            'photographer_first_name',
            'photographer_last_name',
            'retoucher_first_name',
            'retoucher_last_name',
            'stockman',
            'sr_comment',
            's_ph_comment',
            'photo_date',
            'retouch_date'
        ]

    def get_total_products(self, obj):
        # Используем автоматически сгенерированный related_name 'strequestproduct_set'
        return obj.strequestproduct_set.count()

class InvoiceSerializer(serializers.ModelSerializer):
    total_products = serializers.SerializerMethodField()  # Поле для подсчета товаров
    date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")  # Форматируем дату

    def get_total_products(self, obj):
        # Подсчитываем количество товаров в накладной
        return obj.invoiceproduct_set.count()

    # Добавляем поле для отображения имени создателя
    creator = serializers.CharField(source='creator.username', default=None, allow_null=True)

    class Meta:
        model = Invoice
        fields = ['InvoiceNumber', 'date', 'creator', 'total_products']
        
class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductMoveStatus
        fields = ['id', 'name']

class ProductOperationSerializer(serializers.ModelSerializer):
    operation_type_name = serializers.CharField(source='operation_type.name', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    barcode = serializers.CharField(source='product.barcode', read_only=True)

    class Meta:
        model = ProductOperation
        fields = ['barcode', 'product_name', 'user_full_name', 'date', 'comment', 'operation_type_name']

    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}" if obj.user else "Unknown"

class DefectSerializer(serializers.ModelSerializer):
    operation_type_name = serializers.CharField(source='operation_type.name', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    barcode = serializers.CharField(source='product.barcode', read_only=True)
    seller = serializers.IntegerField(source='product.seller', read_only=True)  # или CharField, если поле не числовое

    class Meta:
        model = ProductOperation
        fields = ['barcode', 'product_name', 'user_full_name', 'date', 'comment', 'operation_type_name', 'seller']

    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}" if obj.user else "Unknown"

class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatus
        fields = ['id', 'name']  # Укажите необходимые поля

class OrderProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderProduct
        fields = ['order', 'product', 'assembled', 'assembled_date', 'accepted', 'accepted_date']

class OrderSerializer(serializers.ModelSerializer):
    creator = UserSerializer()  # Include full serializer for the creator
    status = OrderStatusSerializer()  # Include full serializer for the status
    assembly_user = UserSerializer()
    accept_user = UserSerializer()
    total_products = serializers.SerializerMethodField()
    products = OrderProductSerializer(many=True, source='orderproduct_set')  # Include related products
    assembled_count = serializers.SerializerMethodField()
    accepted_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['OrderNumber', 'date', 'status', 'creator', 'total_products', 'products', 'assembly_user', 'assembly_date', 'accept_user', 'accept_date', 'assembled_count', 'accepted_count']

    def get_total_products(self, obj):
        return OrderProduct.objects.filter(order=obj).count()

    def get_assembled_count(self, obj):
        return OrderProduct.objects.filter(order=obj, assembled=True).count()

    def get_accepted_count(self, obj):
        return OrderProduct.objects.filter(order=obj, accepted=True).count()

class RetouchStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetouchStatus
        fields = ['id', 'name']

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'reference_link']

class UserURLsSerializer(serializers.ModelSerializer):
    # Полный вывод информации о пользователе
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = UserURLs
        fields = ['user', 'username', 'email', 'first_name', 'last_name', 'income_url', 'outcome_url']

# Сериализатор для STRequestHistoryOperations
class STRequestHistoryOperationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = STRequestHistoryOperations
        fields = '__all__'

class STRequestHistorySerializer(serializers.ModelSerializer):
    st_request = serializers.StringRelatedField()  # Для отображения номера заявки
    product = serializers.StringRelatedField()  # Для отображения штрихкода продукта
    user = UserSerializer()  # Используем вложенный сериализатор
    operation = serializers.StringRelatedField()  # Для отображения имени операции

    class Meta:
        model = STRequestHistory
        fields = '__all__'

class NofotoListSerializer(serializers.ModelSerializer):
    # Берём штрихкод из связанного товара
    barcode = serializers.CharField(source='product.barcode', read_only=True)
    # Наименование
    name = serializers.CharField(source='product.name', read_only=True)
    # Магазин (seller). Можно назвать "shop_id" или "shop"
    shop = serializers.IntegerField(source='product.seller', read_only=True)
    # Пользователь, внёсший запись (если нужно)
    user = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Nofoto
        fields = [
            'id',
            'barcode',
            'name',
            'shop',
            'date',
            'user',
        ]
