#render.serializers
from rest_framework import serializers
from .models import (
    Product,
    Render,
    RenderCheckResult,
    RetouchStatus,
    ModerationUpload,
    RejectedReason,
    ModerationStudioUpload,
    )
from core.models import (
    PhotoStatus,
    SPhotoStatus
    )


class ProductSerializer(serializers.ModelSerializer):
    # Переопределяем некоторые названия полей для соответствия требуемому формату ответа
    barcode = serializers.CharField(source="Barcode")
    name = serializers.CharField(source="Name")
    
    class Meta:
        model = Product
        fields = [
            "barcode",
            "ProductID",
            "SKUID",
            "name",
            "CategoryName",
            "CategoryID",
            "ShopID",
            "ModerationComment",
            "RejectComment"
        ]

class RenderCheckResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = RenderCheckResult
        fields = ["id", "name"]

class RetouchStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetouchStatus
        fields = ["id", "name"]

class RetoucherRenderSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    product = ProductSerializer(source="Product")
    # Для связи ManyToMany используем many=True
    CheckResult = RenderCheckResultSerializer(many=True)
    RetouchStatus = RetouchStatusSerializer()

    class Meta:
        model = Render
        fields = [
            "id",
            "product",
            "CheckResult",
            "CheckComment",
            "IsSuitable",
            "RetouchStatus",
            "RetouchPhotosLink",
            "RetouchComment",
            "RetouchSeniorComment",
            "ModerationComment",
            "RetouchTimeEnd"
        ]

class SeniorRenderSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    product = ProductSerializer(source="Product")
    CheckResult = RenderCheckResultSerializer(many=True)
    RetouchStatus = RetouchStatusSerializer()
    RetoucherName = serializers.SerializerMethodField()

    class Meta:
        model = Render
        fields = [
            "id",
            "product",
            "CheckResult",
            "CheckComment",
            "CheckTimeStart",
            "IsSuitable",
            "RetouchStatus",
            "RetouchPhotosLink",
            "RetouchComment",
            "RetouchSeniorComment",
            "ModerationComment",
            "RetouchTimeStart",
            "RetouchTimeEnd",
            "RetoucherName"
        ]

    def get_RetoucherName(self, obj):
        if obj.Retoucher:
            # Объединяем first_name и last_name, убираем лишние пробелы
            return f"{obj.Retoucher.first_name} {obj.Retoucher.last_name}".strip()
        return None

# Сериализатор для причин отклонения
class RejectedReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = RejectedReason
        fields = ('id', 'name')

# Основной сериализатор для работы с отклоненными рендерами
class ModerationUploadRejectSerializer(serializers.ModelSerializer):
    # Поля из связанной модели Product (через RenderPhotos)
    Barcode = serializers.CharField(source='RenderPhotos.Product.Barcode', read_only=True)
    ShopID = serializers.IntegerField(source='RenderPhotos.Product.ShopID', read_only=True)
    ProductID = serializers.IntegerField(source='RenderPhotos.Product.ProductID', read_only=True)
    SKUID = serializers.IntegerField(source='RenderPhotos.Product.SKUID', read_only=True)
    Name = serializers.CharField(source='RenderPhotos.Product.Name', read_only=True)

    # Поля из связанной модели Render (через RenderPhotos)
    Retoucher = serializers.SerializerMethodField()
    RetouchTimeEnd = serializers.DateTimeField(source='RenderPhotos.RetouchTimeEnd', format='%d.%m.%Y %H:%M:%S', read_only=True, allow_null=True)
    RetouchPhotosLink = serializers.CharField(source='RenderPhotos.RetouchPhotosLink', read_only=True)
    CheckComment = serializers.CharField(source='RenderPhotos.CheckComment', read_only=True)

    # Поля из ModerationUpload
    RejectedReason = RejectedReasonSerializer(many=True, read_only=True) # Используем вложенный сериализатор
    RejectComment = serializers.CharField(read_only=True)

    class Meta:
        model = ModerationUpload
        fields = (
            'Barcode',
            'ShopID',
            'ProductID',
            'SKUID',
            'Name',
            'Retoucher',
            'RetouchTimeEnd',
            'RetouchPhotosLink',
            'CheckComment',
            'RejectedReason',
            'RejectComment',
            # Добавим ID самого ModerationUpload для возможной идентификации
            'id',
            # Можно добавить и RenderPhotos.id если нужно
            # 'render_id': serializers.IntegerField(source='RenderPhotos.id', read_only=True)
        )

    def get_Retoucher(self, obj):
        """
        Возвращает полное имя ретушера (First Name + Last Name).
        """
        retoucher = obj.RenderPhotos.Retoucher
        if retoucher:
            # Проверяем, есть ли имя и фамилия, чтобы избежать "None None"
            first_name = retoucher.first_name or ""
            last_name = retoucher.last_name or ""
            # Соединяем, убирая лишние пробелы если одно из полей пустое
            full_name = f"{first_name} {last_name}".strip()
            return full_name if full_name else None # Возвращаем None если имя пустое
        return None

class ModerationStudioUploadSerializer(serializers.ModelSerializer):
    barcode = serializers.CharField(source='RenderPhotos.st_request_product.product.barcode', read_only=True)
    sku_id = serializers.CharField(source='RenderPhotos.st_request_product.product.SKUID', read_only=True)
    category_id = serializers.CharField(source='RenderPhotos.st_request_product.product.category.id', read_only=True)
    retouch_link = serializers.CharField(source='RenderPhotos.retouch_link', read_only=True)
    # UploadTimeStart будет включено автоматически, так как это поле модели ModerationStudioUpload

    class Meta:
        model = ModerationStudioUpload
        fields = ['barcode', 'sku_id', 'category_id', 'UploadTimeStart', 'retouch_link']

class ModerationUploadSerializer(serializers.ModelSerializer):
    barcode = serializers.CharField(source='RenderPhotos.Product.Barcode', read_only=True)
    sku_id = serializers.CharField(source='RenderPhotos.Product.SKUID', read_only=True)
    category_id = serializers.CharField(source='RenderPhotos.Product.CategoryID', read_only=True)
    retouch_link = serializers.CharField(source='RenderPhotos.RetouchPhotosLink', read_only=True)
    # UploadTimeStart будет включено автоматически, так как это поле модели ModerationStudioUpload

    class Meta:
        model = ModerationUpload
        fields = ['barcode', 'sku_id', 'category_id', 'UploadTimeStart', 'retouch_link']
