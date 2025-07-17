# hrm/models.py

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

class Department(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название отдела")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Вышестоящий отдел"
    )
    head = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_department',
        verbose_name="Руководитель отдела"
    )

    class Meta:
        verbose_name = "Отдел"
        verbose_name_plural = "Отделы"

    def __str__(self):
        return self.name

class Position(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255, verbose_name="Название должности")
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='positions',
        verbose_name="Отдел"
    )

    class Meta:
        verbose_name = "Должность"
        verbose_name_plural = "Должности"

    def __str__(self):
        return f"{self.name} ({self.department.name})"

class HRMStatus(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, verbose_name="Название статуса")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="Код")

    class Meta:
        verbose_name = "Статус сотрудника"
        verbose_name_plural = "Статусы сотрудников"

    def __str__(self):
        return self.name

class Shift(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, verbose_name="Название смены")
    
    schedule_pattern = models.CharField(
        max_length=50, 
        default="2/2",
        verbose_name="Шаблон графика",
        help_text="Например, '5/2', '2/2', '3/1' и т.д."
    )

    class Meta:
        verbose_name = "Смена"
        verbose_name_plural = "Смены"

    def __str__(self):
        return self.name

class ShiftAssignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shift_assignments', verbose_name="Сотрудник")
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, verbose_name="Смена")
    effective_date = models.DateField(verbose_name="Дата вступления в силу")

    class Meta:
        verbose_name = "Назначение смены"
        verbose_name_plural = "Назначения смен"
        unique_together = ('user', 'effective_date')
        ordering = ['-effective_date']

    def __str__(self):
        return f"{self.user.username} - {self.shift.name} с {self.effective_date}"

    def clean(self):
        if self.effective_date.day != 1:
            raise ValidationError("Дата назначения смены должна быть первым числом месяца.")

class LeaveType(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, verbose_name="Тип отсутствия")

    def __str__(self):
        return self.name

class LeaveRequestStatus(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, verbose_name="Название статуса")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="Код")
    
    class Meta:
        verbose_name = "Статус заявки на отсутствие"
        verbose_name_plural = "Статусы заявок на отсутствие"

    def __str__(self):
        return self.name

class LeaveRequest(models.Model):    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.ForeignKey(
        LeaveRequestStatus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Статус"
    )
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.leave_type.name} ({self.start_date} - {self.end_date})"

class FactualTimeLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='timelogs')
    clock_in = models.DateTimeField(verbose_name="Начало смены")
    clock_out = models.DateTimeField(null=True, blank=True, verbose_name="Конец смены")
    duration = models.DurationField(null=True, blank=True, verbose_name="Продолжительность")
    editor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='edited_timelogs')

    class Meta:
        ordering = ['-clock_in']

    def save(self, *args, **kwargs):
        if self.clock_in and self.clock_out:
            self.duration = self.clock_out - self.clock_in
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Табель {self.user.username} от {self.clock_in.strftime('%Y-%m-%d')}"

class Holiday(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название праздника")
    date = models.DateField(unique=True, verbose_name="Дата")

    class Meta:
        verbose_name = "Праздничный день"
        verbose_name_plural = "Праздничные дни"
        ordering = ['date']

    def __str__(self):
        return f"{self.date.strftime('%Y-%m-%d')} - {self.name}"
