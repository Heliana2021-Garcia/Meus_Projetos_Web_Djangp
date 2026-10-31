from django.db.models import Q
from django.views.generic import ListView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.core.models import RegistoDecisao


class DecisoesView(TipoRequeridoMixin, ListView):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR, Utilizador.Tipo.COORDENADOR)
    template_name = "relatorios/decisoes.html"
    context_object_name = "decisoes"
    paginate_by = 30

    def get_queryset(self):
        qs = RegistoDecisao.objects.all()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(accao__icontains=q) | Q(nome_utilizador__icontains=q)
                | Q(detalhe__icontains=q) | Q(referencia__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["q"] = self.request.GET.get("q", "").strip()
        return contexto