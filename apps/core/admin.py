from django.contrib import admin

from .models import Tecnologia


@admin.register(Tecnologia)
class TecnologiaAdmin(admin.ModelAdmin):
    search_fields = ("nome",)
