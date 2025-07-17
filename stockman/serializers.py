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
    ProductCategory,
    STRequestPhotoTime,
    STRequest,
    STRequestStatus,
    STRequestProduct,
    PhotoStatus,
    SPhotoStatus,
    Invoice,
    InvoiceProduct,
    STRequestType
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
    creation_date = serializers.SerializerMethodField()
    creator = serializers.SerializerMethodField()
    status_id = serializers.IntegerField(source='status.id')
    status_name = serializers.CharField(source='status.name')
    assembly_date = serializers.SerializerMethodField()
    assembly_user = serializers.SerializerMethodField()
    accept_date = serializers.SerializerMethodField()
    accept_date_end = serializers.SerializerMethodField()
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

    def format_datetime(self, dt):
        # Если дата не None, переводим в локальное время с учетом часового пояса и форматируем
        if dt:
            # Если datetime объект не имеет tzinfo, можно сделать его осведомленным,
            # используя текущий часовой пояс, иначе переводим в локальное время.
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            dt = timezone.localtime(dt)
            return dt.strftime("%d.%m.%Y %H:%M:%S")
        return None

    def get_creation_date(self, obj):
        return self.format_datetime(obj.date)

    def get_assembly_date(self, obj):
        return self.format_datetime(obj.assembly_date)

    def get_accept_date(self, obj):
        return self.format_datetime(obj.accept_date)

    def get_accept_date_end(self, obj):
        return self.format_datetime(obj.accept_date_end)

    def get_acceptance_time(self, obj):
        if obj.accept_date and obj.accept_date_end:
            dt_start = timezone.localtime(obj.accept_date) if not timezone.is_naive(obj.accept_date) else timezone.make_aware(obj.accept_date, timezone.get_current_timezone())
            dt_end = timezone.localtime(obj.accept_date_end) if not timezone.is_naive(obj.accept_date_end) else timezone.make_aware(obj.accept_date_end, timezone.get_current_timezone())
            diff = dt_end - dt_start
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
    accepted_date = serializers.SerializerMethodField()

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

    def format_datetime(self, dt):
        if dt:
            # Если datetime объект наивный, делаем его осведомленным
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            # Переводим в локальное время
            dt = timezone.localtime(dt)
            return dt.strftime("%d.%m.%Y %H:%M:%S")
        return None

    def get_accepted_date(self, obj):
        return self.format_datetime(obj.accepted_date)

class STRequestTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = STRequestType
        fields = ('id', 'name')

class OrderDetailSerializer(serializers.ModelSerializer):
    order_number = serializers.IntegerField(source='OrderNumber')
    order_status = serializers.SerializerMethodField()
    creator = serializers.SerializerMethodField()
    assembly_user = serializers.SerializerMethodField()
    accept_user = serializers.SerializerMethodField()
    assembly_date = serializers.SerializerMethodField()
    accept_date = serializers.SerializerMethodField()
    accept_date_end = serializers.SerializerMethodField()
    accept_time = serializers.SerializerMethodField()
    total_products = serializers.SerializerMethodField()
    priority_products = serializers.SerializerMethodField()
    accepted_products = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()  # Дата создания заказа
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

    def format_date(self, dt):
        if dt:
            # Если объект datetime наивный, делаем его осведомленным, используя текущий часовой пояс
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            # Переводим время в локальное с учетом часового пояса
            dt = timezone.localtime(dt)
            return dt.strftime("%d.%m.%Y %H:%M:%S")
        return None

    def get_assembly_date(self, obj):
        return self.format_date(obj.assembly_date)

    def get_accept_date(self, obj):
        return self.format_date(obj.accept_date)

    def get_accept_date_end(self, obj):
        return self.format_date(obj.accept_date_end)

    def get_accept_time(self, obj):
        if obj.accept_date and obj.accept_date_end:
            dt_start = obj.accept_date
            dt_end = obj.accept_date_end
            # Приводим к осведомленным объектам, если необходимо
            if timezone.is_naive(dt_start):
                dt_start = timezone.make_aware(dt_start, timezone.get_current_timezone())
            if timezone.is_naive(dt_end):
                dt_end = timezone.make_aware(dt_end, timezone.get_current_timezone())
            dt_start = timezone.localtime(dt_start)
            dt_end = timezone.localtime(dt_end)
            delta = dt_end - dt_start
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

    def get_date(self, obj):
        return self.format_date(obj.date)

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

class STRequestStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = STRequestStatus
        fields = ('id', 'name')

class STRequestSerializer(serializers.ModelSerializer):
    # Используем наше кастомное поле, которое не преобразует дату в локальное время
    creation_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", read_only=True)
    photo_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", read_only=True, allow_null=True)
    assistant_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", read_only=True, allow_null=True)
    
    # Остальные поля сериализатора
    stockman = serializers.SerializerMethodField()
    photographer = serializers.SerializerMethodField()
    assistant = serializers.SerializerMethodField()
    status = STRequestStatusSerializer(read_only=True)
    products_count = serializers.SerializerMethodField()
    priority_products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = STRequest
        fields = [
            'RequestNumber',
            'creation_date',
            'stockman',
            'status',
            'photographer',
            'photo_date',
            'assistant',
            'assistant_date',
            'products_count',
            'priority_products_count',
            'STRequestType',
            'STRequestTypeBlocked'
        ]
    
    def get_stockman(self, obj):
        if obj.stockman:
            return f"{obj.stockman.first_name} {obj.stockman.last_name}".strip()
        return None

    def get_photographer(self, obj):
        if obj.photographer:
            return f"{obj.photographer.first_name} {obj.photographer.last_name}".strip()
        return None

    def get_assistant(self, obj):
        if obj.assistant:
            return f"{obj.assistant.first_name} {obj.assistant.last_name}".strip()
        return None

    def get_products_count(self, obj):
        return obj.strequestproduct_set.count()

    def get_priority_products_count(self, obj):
        return obj.strequestproduct_set.filter(product__priority=True).count()

class PhotoStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoStatus
        fields = ('id', 'name')

class SPhotoStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = SPhotoStatus
        fields = ('id', 'name')

class STRequestProductDetailSerializer(serializers.ModelSerializer):
    barcode = serializers.CharField(source='product.barcode')
    name = serializers.CharField(source='product.name')
    income_stockman = serializers.SerializerMethodField()
    income_date = TimeZonePreservingDateTimeField(
        source='product.income_date', format="%d.%m.%Y %H:%M:%S", allow_null=True
    )
    photo_status = PhotoStatusSerializer(read_only=True)
    photos_link = serializers.CharField(allow_null=True, required=False)
    sphoto_status = SPhotoStatusSerializer(read_only=True)
    info = serializers.CharField(source='product.info', read_only=True)
    priority = serializers.BooleanField(source='product.priority', read_only=True)
    
    class Meta:
        model = STRequestProduct
        fields = (
            'id', 'barcode', 'name', 'income_stockman', 'income_date',
            'photo_status', 'photos_link', 'sphoto_status', 'info', 'priority'
        )
    
    def get_income_stockman(self, obj):
        user = obj.product.income_stockman
        if user:
            return f"{user.first_name} {user.last_name}".strip()
        return None

class STRequestDetailSerializer(serializers.ModelSerializer):
    creation_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", read_only=True)
    photo_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", read_only=True, allow_null=True)
    stockman = serializers.SerializerMethodField()
    photographer = serializers.SerializerMethodField()
    status = STRequestStatusSerializer(read_only=True)
    STRequestType = STRequestTypeSerializer(read_only=True)
    products_count = serializers.SerializerMethodField()
    STRequestTypeBlocked = serializers.BooleanField(read_only=True)
    priority_products_count = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()    
    class Meta:
        model = STRequest
        fields = [
            'id',
            'RequestNumber',
            'creation_date',
            'status',
            'stockman',
            'photo_date',
            'photographer',
            'STRequestType',
            'STRequestTypeBlocked',
            'products_count',
            'priority_products_count',
            'products'
        ]
    
    def get_stockman(self, obj):
        if obj.stockman:
            return f"{obj.stockman.first_name} {obj.stockman.last_name}".strip()
        return None

    def get_photographer(self, obj):
        if obj.photographer:
            return f"{obj.photographer.first_name} {obj.photographer.last_name}".strip()
        return None

    def get_products_count(self, obj):
        return obj.strequestproduct_set.count()

    def get_priority_products_count(self, obj):
        return obj.strequestproduct_set.filter(product__priority=True).count()

    def get_products(self, obj):
        """
        Получает связанные продукты и сортирует их по id в обратном порядке.
        """
        # Получаем отсортированный queryset
        products_queryset = obj.strequestproduct_set.order_by('-id')
        
        # Сериализуем его с помощью нужного сериализатора
        serializer = STRequestProductDetailSerializer(
            products_queryset, 
            many=True, 
            read_only=True,
            context=self.context # Важно передавать контекст
        )
        return serializer.data

#Сериалайзер листа накладных
class InvoiceSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = ('InvoiceNumber', 'date', 'creator', 'product_count')

    def get_creator(self, obj):
        if obj.creator:
            return f"{obj.creator.first_name} {obj.creator.last_name}"
        return None

    def get_product_count(self, obj):
        return obj.invoiceproduct_set.count()

class ProductDetailSerializer(serializers.Serializer):
    barcode = serializers.CharField(source='product.barcode')
    name = serializers.CharField(source='product.name')
    st_requests = serializers.SerializerMethodField()

    def get_st_requests(self, obj):
        # Для данного продукта получаем все связанные записи STRequestProduct
        # и извлекаем из них номера заявок (RequestNumber)
        st_request_products = obj.product.strequestproduct_set.all()
        return [srp.request.RequestNumber for srp in st_request_products if srp.request]

class InvoiceDetailSerializer(serializers.ModelSerializer):
    creator = serializers.SerializerMethodField()
    date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", allow_null=True)
    product_count = serializers.SerializerMethodField()
    # Используем связь invoiceproduct_set для получения списка продуктов
    products = ProductDetailSerializer(source='invoiceproduct_set', many=True)

    class Meta:
        model = Invoice
        fields = ('InvoiceNumber', 'date', 'creator', 'product_count', 'products')

    def get_creator(self, obj):
        if obj.creator:
            return f"{obj.creator.first_name} {obj.creator.last_name}"
        return None

    def get_product_count(self, obj):
        return obj.invoiceproduct_set.count()
    
class ProductMoveStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductMoveStatus
        fields = ('id', 'name')

class CurrentProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name']

class CurrentSTRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = STRequest
        fields = ['id', 'RequestNumber']

class CurrentProductSerializer(serializers.ModelSerializer):
    income_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", required=False)
    income_stockman = serializers.SerializerMethodField()
    category = CurrentProductCategorySerializer()
    CurrentSTRequest = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'barcode',
            'name',
            'seller',
            'income_date',
            'income_stockman',
            'category',
            'info',
            'priority',
            'CurrentSTRequest',
        ]

    def get_income_stockman(self, obj):
        user = obj.income_stockman
        if user:
            return f"{user.first_name} {user.last_name}"
        return None

    def get_CurrentSTRequest(self, obj):
        strequest_products = obj.strequestproduct_set.filter(request__status__id__in=[2, 3, 5]).select_related('request')
        requests = [srp.request for srp in strequest_products]
        serializer = CurrentSTRequestSerializer(requests, many=True)
        return serializer.data

# Сериализатор полного списка для OrderProduct
class OrderProductSerializer(serializers.ModelSerializer):
    barcode = serializers.CharField(source='product.barcode')
    name = serializers.CharField(source='product.name')
    shop_id = serializers.IntegerField(source='product.seller')
    order_number = serializers.IntegerField(source='order.OrderNumber')
    order_status = serializers.CharField(source='order.status.name')
    creation_date = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    assembly_date = serializers.DateTimeField(source='order.assembly_date', format='%d.%m.%Y %H:%M:%S')
    accept_user = serializers.SerializerMethodField()
    order_accept_date = serializers.DateTimeField(source='order.accept_date', format='%d.%m.%Y %H:%M:%S')
    product_accepted_date = serializers.DateTimeField(source='accepted_date', format='%d.%m.%Y %H:%M:%S')
    accepted = serializers.SerializerMethodField()

    def get_creation_date(self, obj):
        # Дата создания заказа (order.date)
        if obj.order.date:
            return timezone.localtime(obj.order.date).strftime('%d.%m.%Y %H:%M:%S')
        return None

    def get_customer(self, obj):
        # Формирование имени заказчика (FirstName + LastName)
        creator = obj.order.creator
        if creator:
            return f"{creator.first_name} {creator.last_name}"
        return ""

    def get_accept_user(self, obj):
        # Формирование имени пользователя, принявшего заказ
        accept_user = obj.order.accept_user
        if accept_user:
            return f"{accept_user.first_name} {accept_user.last_name}"
        return ""

    def get_accepted(self, obj):
        # Принят: "да" или "нет"
        return "да" if obj.accepted else "нет"

    class Meta:
        model = OrderProduct
        fields = [
            'barcode',
            'name',
            'shop_id',
            'order_number',
            'order_status',
            'creation_date',
            'customer',
            'assembly_date',
            'accept_user',
            'order_accept_date',
            'product_accepted_date',
            'accepted',
        ]

#проблемная категория 1
class ProblematicProduct1Serializer(serializers.ModelSerializer):
    # Форматируем дату в нужный вид
    income_date = serializers.DateTimeField(format="%d.%m.%Y %H:%M:%S", read_only=True)
    # Поле для имени и фамилии кладовщика
    income_stockman = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = (
            'barcode',
            'name',
            'income_date',
            'income_stockman',
            'info',
            'priority'
        )

    def get_income_stockman(self, obj):
        """
        Возвращает имя и фамилию кладовщика, принявшего товар.
        """
        if obj.income_stockman:
            # Собираем имя и фамилию из стандартной модели User
            # Убираем лишние пробелы, если одно из полей пустое
            return f"{obj.income_stockman.first_name} {obj.income_stockman.last_name}".strip()
        return None # Или можно вернуть пустую строку ""
    
class ProblematicProduct2Serializer(serializers.ModelSerializer):
    # Форматируем дату
    income_date = serializers.DateTimeField(format="%d.%m.%Y %H:%M:%S", read_only=True)
    # Форматируем имя кладовщика
    income_stockman = serializers.SerializerMethodField(read_only=True)
    # Поле для списка номеров заявок
    strequestlist = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = (
            'barcode',
            'name',
            'income_date',
            'income_stockman',
            'info',
            'priority',
            'strequestlist' # Добавили новое поле
        )

    def get_income_stockman(self, obj):
        """
        Возвращает имя и фамилию кладовщика, принявшего товар.
        """
        if obj.income_stockman:
            return f"{obj.income_stockman.first_name} {obj.income_stockman.last_name}".strip()
        return None

    def get_strequestlist(self, obj):
        """
        Возвращает список номеров заявок (RequestNumber) со статусом 2 или 3,
        в которых присутствует данный продукт (obj).
        Данные будут браться из предзагруженной карты в контексте сериализатора
        для предотвращения N+1 запросов.
        """
        # Получаем предзагруженную карту из контекста
        # Ключ - ID продукта, значение - список номеров заявок
        request_map = self.context.get('product_request_map', {})
        # Возвращаем список для текущего продукта или пустой список, если его нет в карте
        return request_map.get(obj.id, [])

#Товары, отснятые более суток назад, но не отправленные
class ProblematicProduct3Serializer(serializers.ModelSerializer):
    income_date = TimeZonePreservingDateTimeField(format="%d.%m.%Y %H:%M:%S", read_only=True, allow_null=True)
    income_stockman = serializers.SerializerMethodField(read_only=True)
    strequest = serializers.CharField(source='target_strequest_number', read_only=True)
    product_move_status_name = serializers.CharField(source='move_status.name', read_only=True, allow_null=True)
    st_request_check_time = TimeZonePreservingDateTimeField(
        format="%d.%m.%Y %H:%M:%S",
        read_only=True,
        source='target_strequest_check_time',
        allow_null=True
    )
    
    # Изменяем на SerializerMethodField
    st_request_product_photo_date = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'barcode',
            'name',
            'product_move_status_name',
            'income_date',
            'income_stockman',
            'info',
            'priority',
            'strequest',
            'st_request_check_time',
            'st_request_product_photo_date' 
        )

    def get_income_stockman(self, obj):
        if obj.income_stockman:
            return f"{obj.income_stockman.first_name} {obj.income_stockman.last_name}".strip()
        return None

    def get_st_request_product_photo_date(self, obj):
        # obj - это экземпляр Product, у которого теперь есть аннотация annotated_target_strequest_id
        target_strequest_id = getattr(obj, 'annotated_target_strequest_id', None)
        if not target_strequest_id:
            return None

        try:
            # Находим STRequestProduct, который связывает текущий продукт (obj.id)
            # и целевую заявку (target_strequest_id)
            st_request_product = STRequestProduct.objects.filter(
                product_id=obj.id,
                request_id=target_strequest_id
            ).first() # Предполагаем, что такая связь уникальна или берем первую

            if st_request_product:
                # Теперь ищем STRequestPhotoTime для этого STRequestProduct
                photo_time_entry = STRequestPhotoTime.objects.filter(
                    st_request_product=st_request_product,
                    # photo_date__isnull=False # Можно убрать, если дата всегда есть
                ).order_by('photo_date').first() # Берем самую раннюю

                if photo_time_entry and photo_time_entry.photo_date:
                    # Форматируем дату так же, как TimeZonePreservingDateTimeField
                    # Используем существующий TimeZonePreservingDateTimeField для консистентности, если это возможно,
                    # или форматируем вручную.
                    # Для простоты, отформатируем вручную с учетом локализации:
                    local_photo_date = timezone.localtime(photo_time_entry.photo_date)
                    return local_photo_date.strftime("%d.%m.%Y %H:%M:%S")
            return None
        except Exception as e:
            # Логирование ошибки может быть полезно
            print(f"Error in get_st_request_product_photo_date: {e}")
            return None
