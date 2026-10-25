from django.contrib import admin

from .models import Notificacao, Tecnologia


@admin.register(Tecnologia)
class TecnologiaAdmin(admin.ModelAdmin):
    search_fields = ("nome",)


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "destinatario", "lida", "criado_em")
    list_filter = ("lida",)
    search_fields = ("titulo", "destinatario__username")