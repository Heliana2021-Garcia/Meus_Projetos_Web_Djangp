from django.contrib import admin

from .models import Empresa


@admin.action(description="Validar o NIF das empresas seleccionadas")
def validar_nifs(modeladmin, request, queryset):
    for empresa in queryset:
        empresa.validar_nif()


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "nif", "tipo", "nif_validado", "validado_em")
    list_filter = ("tipo", "nif_validado")
    search_fields = ("nome", "nif")
    actions = [validar_nifs]
