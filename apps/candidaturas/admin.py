from django.contrib import admin

from .models import Candidatura


@admin.register(Candidatura)
class CandidaturaAdmin(admin.ModelAdmin):
    list_display = ("estudante", "vaga", "estado", "avaliacao_final", "criado_em")
    list_filter = ("estado", "vaga__empresa")
    search_fields = ("estudante__numero_estudante", "vaga__titulo")
    # As mudanças de estado passam pelos métodos do modelo (regras do Kanban)
    readonly_fields = ("estado", "feedback", "avaliacao_final", "concluida_em")
