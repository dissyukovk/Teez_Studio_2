from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User, Group


#Скрипты РГТ
class RGTScripts(models.Model):
    OKZReorderEnable = models.BooleanField(default=True, verbose_name="Сброс заказов ОКЗ")
    OKZReorderTreshold = models.DurationField(null=True, blank=True, verbose_name="Отсечка сброса")
    OldProductsPriorityEnable = models.BooleanField(default=True, verbose_name="Выставление приоритетов по времени приемки")
    OldProductsPriorityTreshold = models.DurationField(null=True, blank=True, verbose_name="Отсечка выставления приоритетов")

    class Meta:
        verbose_name = "Настройки управления скриптами РГТ"
        verbose_name_plural = "Настройки управления скриптами"

    def save(self, *args, **kwargs):
        if not self.pk and RGTScripts.objects.exists():
            # Если это новая запись и уже существует другая запись, запрещаем сохранение.
            raise ValidationError('Может существовать только один экземпляр настроек RGTScripts.')
        return super(RGTScripts, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Опционально: можно запретить удаление единственной записи,
        # если вам нужно, чтобы она всегда существовала.
        # В этом случае раскомментируйте следующую строку и измените сообщение:
        raise ValidationError('Нельзя удалить единственный экземпляр настроек RGTScripts.')
        return super(RGTScripts, self).delete(*args, **kwargs)

    @classmethod
    def load(cls):
        # Удобный метод для получения единственного экземпляра настроек.
        # Если экземпляр не существует, он будет создан с настройками по умолчанию.
        obj, created = cls.objects.get_or_create(pk=1) # Используем pk=1 для определенности
        return obj
