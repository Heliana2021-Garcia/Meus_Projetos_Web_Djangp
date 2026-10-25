from django.views.generic import TemplateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador

from .models import Empresa


class PainelEmpresaView(TipoRequeridoMixin, TemplateView):
    template_name = "empresas/painel.html"
    tipos_permitidos = (Utilizador.Tipo.EMPRESA,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["empresa"] = Empresa.objects.filter(utilizador=self.request.user).first()
        return contexto