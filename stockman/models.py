from django.db import models
from core.models import Product
from django.contrib.auth.models import User, Group

class ProblemInvoice(models.Model):
    id = models.BigIntegerField(primary_key=True)
    date = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return self.InvoiceNumber

class ProblemInvoiceProduct(models.Model):
    invoice = models.ForeignKey(ProblemInvoice, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1, verbose_name="Количество")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
