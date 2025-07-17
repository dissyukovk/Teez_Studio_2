#render.models
from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from core.models import RetouchRequestProduct

#Основная модель продукта
class Product(models.Model):
    Barcode = models.CharField(max_length=13, unique=True)
    ProductID = models.BigIntegerField(null=True, blank=True)
    SKUID = models.BigIntegerField(null=True, blank=True)
    Name = models.CharField(max_length=500, null=True, blank=True)
    CategoryName = models.CharField(max_length=64, blank=True, null=True)
    CategoryID = models.BigIntegerField(null=True, blank=True)
    ShopID = models.BigIntegerField(null=True, blank=True)
    ShopType = models.CharField(max_length=4, blank=True, null=True)
    ShopName = models.CharField(max_length=512, blank=True, null=True)
    ProductStatus = models.CharField(max_length=64, blank=True, null=True)
    ProductModerationStatus = models.CharField(max_length=64, blank=True, null=True)
    PhotoModerationStatus = models.CharField(max_length=64, blank=True, null=True)
    SKUStatus = models.CharField(max_length=64, blank=True, null=True)
    WMSQuantity = models.BigIntegerField(null=True, blank=True)

    RetouchComment = models.TextField(blank=True, null=True)
    RetouchCommentDate = models.DateTimeField(null=True, blank=True)
    RetouchSeniorComment = models.TextField(blank=True, null=True)
    RetouchSeniorCommentTime = models.DateTimeField(null=True, blank=True)
    ModerationComment = models.TextField(blank=True, null=True)
    ModerationCommentTime = models.DateTimeField(null=True, blank=True)
    RejectComment = models.TextField(blank=True, null=True)
    RejectCommentTime = models.DateTimeField(null=True, blank=True)

    IsRetouchBlock = models.BooleanField(default=False)
    IsModerationBlock = models.BooleanField(default=False)

    IsOnRender = models.BooleanField(default=False)

    IsOnOrder = models.BooleanField(default=False)
    
    priority = models.IntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.Barcode}"

    def save(self, *args, **kwargs):
        # Если объект уже существует, получаем предыдущие значения для сравнения
        if self.pk:
            previous = Product.objects.get(pk=self.pk)
            if self.RetouchComment != previous.RetouchComment:
                self.RetouchCommentDate = timezone.now()
            if self.RetouchSeniorComment != previous.RetouchSeniorComment:
                self.RetouchSeniorCommentTime = timezone.now()
            if self.ModerationComment != previous.ModerationComment:
                self.ModerationCommentTime = timezone.now()
            if self.RejectComment != previous.RejectComment:
                self.RejectCommentTime = timezone.now()
        else:
            # Новый объект: если комментарий задан, устанавливаем дату
            if self.RetouchComment and not self.RetouchCommentDate:
                self.RetouchCommentDate = timezone.now()
            if self.RetouchSeniorComment and not self.RetouchSeniorCommentTime:
                self.RetouchSeniorCommentTime = timezone.now()
            if self.ModerationComment and not self.ModerationCommentTime:
                self.ModerationCommentTime = timezone.now()
            if self.RejectComment and not self.RejectCommentTime:
                self.RejectCommentTime = timezone.now()
        super().save(*args, **kwargs)

#результаты проверки
class RenderCheckResult(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64, blank=True, null=True)

    def __str__(self):
        return f"{self.id} - {self.name}"

#статус ретуши/рендера
class RetouchStatus(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64, blank=True, null=True)

    def __str__(self):
        return f"{self.id} - {self.name}"

#Статус проверки старшим ретушером
class SeniorRetouchStatus(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64, blank=True, null=True)

    def __str__(self):
        return f"{self.id} - {self.name}"

#модель для рендера
class Render(models.Model):
    Product = models.ForeignKey(Product, on_delete=models.CASCADE)
    
    Retoucher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ретушёр")
    
    CheckResult = models.ManyToManyField(RenderCheckResult, blank=True, verbose_name="Результат проверки")
    CheckTimeStart = models.DateTimeField(null=True, blank=True, verbose_name="Дата начала проверки")
    CheckTimeEnd = models.DateTimeField(null=True, blank=True, verbose_name="Дата окончания проверки")
    CheckDuration = models.DurationField(null=True, blank=True, verbose_name="Длительность проверки")
    CheckComment = models.TextField(blank=True, null=True)
    IsSuitable = models.BooleanField(null=True, verbose_name="Подходит для рендера")
    
    RetouchStatus = models.ForeignKey(RetouchStatus, on_delete=models.SET_NULL, null=True, blank=True)
    RetouchTimeStart = models.DateTimeField(null=True, blank=True, verbose_name="Дата начала рендера")
    RetouchTimeEnd = models.DateTimeField(null=True, blank=True, verbose_name="Дата загрузки фото")
    RetouchDuration = models.DurationField(null=True, blank=True, verbose_name="Длительность рендера")
    RetouchPhotosLink = models.CharField(max_length=512, blank=True, null=True)
    RetouchSeniorStatus = models.ForeignKey(SeniorRetouchStatus, on_delete=models.SET_NULL, null=True, blank=True)
    RetouchComment = models.TextField(blank=True, null=True)
    RetouchSeniorComment = models.TextField(blank=True, null=True)
    ModerationComment = models.TextField(blank=True, null=True)

    IsOnUpload = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return f"{self.Product.Barcode}"

    def save(self, *args, **kwargs):
        # Если установлены CheckTimeStart и CheckTimeEnd, вычисляем длительность проверки
        if self.CheckTimeStart and self.CheckTimeEnd:
            self.CheckDuration = self.CheckTimeEnd - self.CheckTimeStart
        
        # Если установлены RetouchTimeStart и RetouchTimeEnd, вычисляем длительность рендера
        if self.RetouchTimeStart and self.RetouchTimeEnd:
            self.RetouchDuration = self.RetouchTimeEnd - self.RetouchTimeStart
        
        super().save(*args, **kwargs)

#Причины отклонения от модерации
class RejectedReason(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64, blank=True, null=True)

    def __str__(self):
        return f"{self.id} - {self.name}"

#Причины отклонения для студийных фото
class StudioRejectedReason(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64, blank=True, null=True)

    def __str__(self):
        return f"{self.id} - {self.name}"

#Статусы загрузки
class UploadStatus(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64, blank=True, null=True)

    def __str__(self):
        return f"{self.id} - {self.name}"

#загрузка модерацией
class ModerationUpload(models.Model):
    RenderPhotos = models.ForeignKey(Render, on_delete=models.CASCADE)

    Moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Модератор")
    UploadTimeStart = models.DateTimeField(null=True, blank=True, verbose_name="Дата начала загрузки")
    UploadTimeEnd = models.DateTimeField(null=True, blank=True, verbose_name="Дата окончания загрузки")
    UploadTime = models.DurationField(null=True, blank=True, verbose_name="Длительность загрузки")
    UploadStatus = models.ForeignKey(UploadStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Статус загрузки")

    IsUploaded = models.BooleanField(null=True, verbose_name="Загружено")
    IsRejected = models.BooleanField(null=True, verbose_name="Отклонено")
    RejectedReason = models.ManyToManyField(RejectedReason, blank=True, verbose_name="Причина отклонения")
    RejectComment = models.TextField(blank=True, null=True)
    ReturnToRender = models.BooleanField(default=False, verbose_name="Вернуть ретушерам")
    ReturnToRenderComplete = models.BooleanField(default=False, verbose_name="Ретушеры забрали")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def save(self, *args, **kwargs):
        if self.UploadTimeStart and self.UploadTimeEnd:
            self.UploadTime = self.UploadTimeEnd - self.UploadTimeStart
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.RenderPhotos.Product.Barcode}"

#загрузка модерацией фото от фс
class ModerationStudioUpload(models.Model):
    RenderPhotos = models.ForeignKey(RetouchRequestProduct, on_delete=models.CASCADE)

    Moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Модератор")
    UploadTimeStart = models.DateTimeField(null=True, blank=True, verbose_name="Дата начала загрузки")
    UploadTimeEnd = models.DateTimeField(null=True, blank=True, verbose_name="Дата окончания загрузки")
    UploadTime = models.DurationField(null=True, blank=True, verbose_name="Длительность загрузки")
    UploadStatus = models.ForeignKey(UploadStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Статус загрузки")

    IsUploaded = models.BooleanField(null=True, verbose_name="Загружено")
    IsRejected = models.BooleanField(null=True, verbose_name="Отклонено")
    RejectedReason = models.ManyToManyField(StudioRejectedReason, blank=True, verbose_name="Причина отклонения")
    RejectComment = models.TextField(blank=True, null=True)
    ReturnToRender = models.BooleanField(default=False, verbose_name="Вернуть ретушерам")
    ReturnToRenderComplete = models.BooleanField(default=False, verbose_name="Ретушеры забрали")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def save(self, *args, **kwargs):
        if self.UploadTimeStart and self.UploadTimeEnd:
            self.UploadTime = self.UploadTimeEnd - self.UploadTimeStart
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.RenderPhotos.st_request_product.product.barcode}"
