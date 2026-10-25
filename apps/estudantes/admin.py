from django.contrib import admin

from .models import Curso, PerfilEstudante


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla")


@admin.register(PerfilEstudante)
class PerfilEstudanteAdmin(admin.ModelAdmin):
    list_display = ("utilizador", "numero_estudante", "curso", "ano_frequencia", "media_geral", "estado")
    list_filter = ("curso", "ano_frequencia", "estado")
    search_fields = ("numero_estudante", "utilizador__first_name", "utilizador__last_name")
    filter_horizontal = ("tecnologias",)
