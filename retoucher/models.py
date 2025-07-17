from django.db import models
from django.contrib.auth.models import User, Group
from core.models import RetouchRequestProduct, RetouchRequest

# Create your models here.
class RetouchRequestEdits(models.Model):
    RetouchRequestProduct = models.ForeignKey(RetouchRequestProduct, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True, null=True)
    retoucher = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='Ретушер', blank=True, null=True)
    SeniorRetoucher = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='Старший_ретушер', blank=True, null=True)
    
