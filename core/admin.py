from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry
from .models import (
    STRequest,
    STRequestProduct,
    STRequestType,
    Product,
    ProductCategory,
    ProductMoveStatus,
    RetouchStatus,
    SRetouchStatus,
    Order,
    OrderProduct,
    OrderStatus,
    Invoice,
    InvoiceProduct,
    STRequestStatus,
    ProductOperation,
    ProductOperationTypes,
    UserURLs,
    STRequestHistory,
    STRequestHistoryOperations,
    PhotoStatus,
    Camera,
    UserProfile,
    RetouchRequestStatus,
    RetouchRequest,
    ShootingToRetouchLink,
    RetouchRequestProduct,
    SPhotoStatus,
    STRequestPhotoTime,
    Blocked_Shops,
    Nofoto,
    Blocked_Barcode,
    APIKeys,
    )


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('action_time', 'user', 'content_type', 'object_repr', 'action_flag')
    list_filter = ('user', 'action_flag')

# Admin for STRequestStatus
@admin.register(STRequestStatus)
class STRequestStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']

# Admin for STRequestType
@admin.register(STRequestType)
class STRequestTypeAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']

# Admin for STRequest
@admin.register(STRequest)
class STRequestAdmin(admin.ModelAdmin):
    list_display = [
        'RequestNumber', 'photographer', 'retoucher', 'stockman',
        'creation_date', 'status', 'photo_date', 'retouch_date'
    ]
    search_fields = ['RequestNumber', 'status__name']
    list_filter = ['status', 'creation_date', 'photo_date']
    ordering = ['creation_date']

# Admin for STRequestProduct
@admin.register(STRequestProduct)
class STRequestProductAdmin(admin.ModelAdmin):
    list_display = ['request', 'product', 'photo_status', 'photos_link', 'sphoto_status', 'comment']
    search_fields = ['request__RequestNumber', 'product__barcode'] 
    list_filter = ['photo_status', 'sphoto_status', 'request__status']
    raw_id_fields = ['product']
    ordering = ['request']

# Admin for Product
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['barcode', 'SKUID', 'name', 'category', 'seller', 'move_status', 'income_date', 'outcome_date', 'info', 'ProductStatus', 'PhotoModerationStatus']
    search_fields = ['barcode', 'ProductStatus', 'PhotoModerationStatus', 'SKUID']
    list_filter = ['move_status']
    ordering = ['name']

# Admin for ProductCategory
@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'reference_link', 'IsBlocked', 'IsReference', 'STRequestType', 'updated_at']
    search_fields = ['id', 'name']
    list_filter = ['IsBlocked', 'IsReference', 'STRequestType', 'updated_at']
    ordering = ['-id']

# Admin for ProductMoveStatus
@admin.register(ProductMoveStatus)
class ProductMoveStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']
    ordering = ['id']

# Admin for RetouchStatus
@admin.register(RetouchStatus)
class RetouchStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['id', 'name']
    ordering = ['id']

# Admin for SRetouchStatus
@admin.register(SRetouchStatus)
class SRetouchStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['id', 'name']
    ordering = ['id']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['OrderNumber', 'date', 'creator', 'status']
    search_fields = ['OrderNumber']
    list_filter = ['status']
    ordering = ['-OrderNumber']

@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['id']

@admin.register(OrderProduct)
class OrderProductAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'assembled', 'assembled_date', 'accepted', 'accepted_date']
    search_fields = ['order__OrderNumber', 'product__barcode']
    raw_id_fields = ['product']
    ordering = ['order']

# Admin for Invoice
@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['InvoiceNumber', 'date', 'creator']
    search_fields = ['InvoiceNumber']
    ordering = ['date']

# Admin for InvoiceProduct
@admin.register(InvoiceProduct)
class InvoiceProductAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'product']
    search_fields = ['invoice__InvoiceNumber', 'product__barcode']
    raw_id_fields = ['product']
    ordering = ['invoice']

# Admin для ProductOperation
@admin.register(ProductOperation)
class ProductOperationAdmin(admin.ModelAdmin):
    list_display = ('product', 'operation_type', 'user', 'date', 'comment')
    list_filter = ('operation_type', 'date')
    raw_id_fields = ['product']
    search_fields = ('product__barcode', 'operation_type__name', 'user__username')

@admin.register(ProductOperationTypes)
class ProductOperationTypesAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    
@admin.register(UserURLs)
class UserURLsAdmin(admin.ModelAdmin):
    list_display = ('user', 'income_url', 'outcome_url')

@admin.register(STRequestHistoryOperations)
class STRequestHistoryOperationsAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('id', 'name',)

@admin.register(STRequestHistory)
class STRequestHistoryAdmin(admin.ModelAdmin):
    list_display = ('st_request', 'product', 'user', 'date', 'operation')
    search_fields = ('st_request__RequestNumber', 'product__barcode', 'user__username', 'operation__name')
    list_filter = ('operation', 'date')

# Admin for PhotoStatus
@admin.register(PhotoStatus)
class PhotoStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    ordering = ('id',)

# Admin for PhotoStatus
@admin.register(SPhotoStatus)
class SPhotoStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)
    ordering = ('id',)

# Admin for Camera
@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ('id', 'IP')
    search_fields = ('IP',)

# Снимаем стандартную регистрацию User
admin.site.unregister(User)

# Inline для профиля
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fk_name = 'user'
    can_delete = False
    verbose_name_plural = 'User Profile'
    list_filter = ('on_work')
    fields = ('telegram_name', 'telegram_id', 'phone_number', 'birth_date', 'on_work', 'avatar', 'position', 'supervisor', 'hire_date')

# Кастомизация админки пользователя
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)

    def add_view(self, *args, **kwargs):
        self.inlines = (UserProfileInline,)
        return super().add_view(*args, **kwargs)

    def change_view(self, *args, **kwargs):
        self.inlines = (UserProfileInline,)
        return super().change_view(*args, **kwargs)

# Регистрация модели RetouchRequestStatus
@admin.register(RetouchRequestStatus)
class RetouchRequestStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')  # Отображаемые поля в списке
    search_fields = ('id',)      # Поиск по имени


# Регистрация модели RetouchRequest
@admin.register(RetouchRequest)
class RetouchRequestAdmin(admin.ModelAdmin):
    list_display = ('RequestNumber', 'retoucher', 'creation_date', 'retouch_date', 'status', 'priority', 'comments')
    search_fields = ('RequestNumber', 'retoucher__username')
    list_filter = ('status', 'creation_date', 'retouch_date', 'priority')
    ordering = ('-creation_date',)
    autocomplete_fields = ('status',)

# Регистрация модели ShootingToRetouchLink
@admin.register(ShootingToRetouchLink)
class ShootingToRetouchLinkAdmin(admin.ModelAdmin):
    list_display = ('shooting_request', 'retouch_request')
    raw_id_fields = ('shooting_request', 'retouch_request')

# Регистрация модели RetouchRequestProduct
@admin.register(RetouchRequestProduct)
class RetouchRequestProductAdmin(admin.ModelAdmin):
    # Поле product заменено на get_product_barcode для отображения штрихкода товара
    list_display = ('retouch_request', 'get_product_barcode', 'retouch_status', 'retouch_link', 'sretouch_status', 'comment')
    # Поиск по штрихкоду будет через цепочку st_request_product__product__barcode
    search_fields = ('st_request_product__product__barcode', 'retouch_request__RequestNumber')
    list_filter = ('retouch_status', 'sretouch_status')
    # Заменяем product на st_request_product в raw_id_fields
    raw_id_fields = ('st_request_product',)
    autocomplete_fields = ('retouch_status',)

    def get_product_barcode(self, obj):
        # Отображаем штрихкод продукта через связанный st_request_product
        if obj.st_request_product and obj.st_request_product.product:
            return obj.st_request_product.product.barcode
        return ''
    get_product_barcode.short_description = "Product Barcode"

@admin.register(STRequestPhotoTime)
class STRequestPhotoTimeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "request_number",       # метод, возвращающий номер заявки
        "product_barcode",      # метод, возвращающий штрихкод
        "photo_date",
        "user",
    )
    search_fields = (
        "st_request_product__request__RequestNumber", 
        "st_request_product__product__barcode",
    )
    list_filter = ( 
        "user",
        "photo_date",
        "user__username"
    )
    date_hierarchy = "photo_date"
    ordering = ("photo_date",)

    def request_number(self, obj):
        """
        Возвращает номер заявки, связанный через st_request_product.
        """
        # Убедитесь, что поле называется request
        return obj.st_request_product.request.RequestNumber if obj.st_request_product and obj.st_request_product.request else None
    request_number.short_description = "Request Number"

    def product_barcode(self, obj):
        """
        Возвращает штрихкод продукта, связанный через st_request_product.
        """
        # Убедитесь, что поле называется product
        return obj.st_request_product.product.barcode if obj.st_request_product and obj.st_request_product.product else None
    product_barcode.short_description = "Product Barcode"

@admin.register(Blocked_Shops)
class BlockedShopsAdmin(admin.ModelAdmin):
    list_display = ('id', 'shop_id')
    search_fields = ('id', 'shop_id')

@admin.register(Nofoto)
class NofotoAdmin(admin.ModelAdmin):
    list_display = ('product', 'date', 'user')
    list_filter = ('date',)
    search_fields = ('product__barcode', 'product__seller')
    date_hierarchy = 'date'
    ordering = ('-date',)

@admin.register(Blocked_Barcode)
class BlockedBarcodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'barcode')
    search_fields = ('id', 'barcode')

@admin.register(APIKeys)
class APIKeysAdmin(admin.ModelAdmin):
    list_display = ('id', 'key')
    search_fields = ('id', 'key')
