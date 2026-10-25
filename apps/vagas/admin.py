from django.contrib import admin

from .models import Vaga


@admin.action(description="Publicar as vagas seleccionadas")
def publicar_vagas(modeladmin, request, queryset):
    for vaga in queryset:
        try:
            vaga.publicar()
        except Exception as erro:
            modeladmin.message_user(request, f"{vaga}: {'; '.join(erro.messages)}", level="error")


@admin.register(Vaga)
class VagaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "empresa", "estado", "numero_vagas", "data_limite")
    list_filter = ("estado", "modalidade", "empresa__tipo")
    search_fields = ("titulo", "empresa__nome")
    filter_horizontal = ("cursos", "tecnologias")
    actions = [publicar_vagas]
