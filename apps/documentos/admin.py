from django.contrib import admin

from .models import CartaEncaminhamento


@admin.register(CartaEncaminhamento)
class CartaEncaminhamentoAdmin(admin.ModelAdmin):
    list_display = ("referencia", "candidatura", "emitida_por", "emitida_em")
    search_fields = ("candidatura__estudante__numero_estudante",)
    readonly_fields = ("candidatura", "ano", "sequencia", "emitida_por", "emitida_em")

    def has_add_permission(self, request):
        return False