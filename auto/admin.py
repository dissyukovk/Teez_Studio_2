from django.contrib import admin
from . import models

# Admin for RGTScripts
@admin.register(models.RGTScripts)
class RGTScriptsAdmin(admin.ModelAdmin):
    list_display = ['id', 'OKZReorderEnable', 'OKZReorderTreshold', 'OldProductsPriorityEnable', 'OldProductsPriorityTreshold']
