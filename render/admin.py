from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry

from . import models

# --- Кастомный фильтр для CheckResult ---
class CheckResultListFilter(admin.SimpleListFilter):
    title = 'Результат проверки' # Заголовок в админке
    parameter_name = 'check_result_id' # Имя параметра в URL

    def lookups(self, request, model_admin):
        """
        Возвращает список кортежей (id, название) для всех RenderCheckResult.
        Эти кортежи будут использоваться для создания ссылок фильтра.
        """
        # Получаем все возможные результаты проверки
        results = models.RenderCheckResult.objects.all()
        # Формируем список для отображения в фильтре
        return [(result.id, str(result)) for result in results]

    def queryset(self, request, queryset):
        """
        Фильтрует основной QuerySet (Render) на основе выбранного значения.
        self.value() содержит id выбранного RenderCheckResult.
        """
        if self.value(): # Если значение выбрано (не 'All')
            # Фильтруем Render, у которых в CheckResult есть объект с данным id
            return queryset.filter(CheckResult__id=self.value())
        else:
            # Если значение не выбрано, возвращаем исходный queryset
            return queryset

# Admin for Product
@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['Barcode', 'Name', 'ShopID', 'ShopType', 'PhotoModerationStatus', 'IsOnRender', 'IsRetouchBlock', 'IsOnOrder']
    search_fields = ['Barcode']
    list_filter = ['PhotoModerationStatus', 'IsOnRender', 'IsOnOrder']

# Admin for RenderCheckResult
@admin.register(models.RenderCheckResult)
class RenderCheckResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['id', 'name']

# Admin for RetouchStatus
@admin.register(models.RetouchStatus)
class RetouchStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['id', 'name']

# Admin for SeniorRetouchStatus
@admin.register(models.SeniorRetouchStatus)
class SeniorRetouchStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['id', 'name']

# Admin for Render
@admin.register(models.Render)
class RenderAdmin(admin.ModelAdmin):
    list_display = ['Product', 'Retoucher', 'get_CheckResult', 'RetouchStatus']
    search_fields = ['Product__Barcode']
    raw_id_fields = ['Product']
    list_filter = [
        CheckResultListFilter, 
        'RetouchStatus',       
        'IsSuitable',
        'CheckTimeStart',
        'Retoucher'
    ]

    def get_CheckResult(self, obj):
        return ", ".join([str(result) for result in obj.CheckResult.all()])
    get_CheckResult.short_description = 'Результаты проверки'

# Admin for UploadStatus
@admin.register(models.UploadStatus)
class UploadStatusAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['id', 'name']

# Admin for RejectedReason
@admin.register(models.RejectedReason)
class RejectedReasonAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['id', 'name']

# Admin for StudioRejectedReason
@admin.register(models.StudioRejectedReason)
class StudioRejectedReasonAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['id', 'name']

# Admin for ModerationUpload
@admin.register(models.ModerationUpload)
class ModerationUploadAdmin(admin.ModelAdmin):
    list_display = ['RenderPhotos', 'Moderator', 'IsUploaded', 'get_RejectedReason', 'RejectComment', 'RenderPhotos__RetouchPhotosLink']
    search_fields = ['RenderPhotos__Product__Barcode']
    raw_id_fields = ['RenderPhotos']
    list_filter = ['IsUploaded', 'UploadStatus', 'UploadTimeStart', 'RejectedReason', 'ReturnToRenderComplete']

    def get_RejectedReason(self, obj):
        # Получаем все связанные объекты и объединяем их строковые представления через запятую
        return ", ".join([str(result) for result in obj.RejectedReason.all()])
    get_RejectedReason.short_description = 'Результаты проверки'

# Admin for ModerationStudioUpload
@admin.register(models.ModerationStudioUpload)
class ModerationStudioUploadAdmin(admin.ModelAdmin):
    list_display = ['RenderPhotos', 'Moderator', 'IsUploaded', 'get_RejectedReason', 'RejectComment', 'RenderPhotos__retouch_link']
    search_fields = ['RenderPhotos__st_request_product__product__barcode']
    raw_id_fields = ['RenderPhotos']
    list_filter = ['IsUploaded', 'UploadStatus', 'UploadTimeStart', 'RejectedReason', 'ReturnToRenderComplete']

    def get_RejectedReason(self, obj):
        # Получаем все связанные объекты и объединяем их строковые представления через запятую
        return ", ".join([str(result) for result in obj.RejectedReason.all()])
    get_RejectedReason.short_description = 'Результаты проверки'
