from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from apps.candidaturas.models import Candidatura
from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.vagas.mixins import EmpresaRequeridaMixin

from .forms import OrientadorForm
from .models import Orientador


class OrientadoresEmpresaView(EmpresaRequeridaMixin, FormView):
    template_name = "empresas/orientadores.html"
    form_class = OrientadorForm
    success_url = reverse_lazy("empresas:orientadores")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["empresa"] = self.empresa
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["orientadores"] = Orientador.objects.filter(empresa=self.empresa).select_related("utilizador")
        return contexto

    def form_valid(self, form):
        orientador = form.save()
        messages.success(
            self.request,
            f"Orientador {orientador.utilizador.get_full_name()} criado. "
            "Entra com o nome de utilizador e a palavra-passe que definiu.",
        )
        return super().form_valid(form)


class PainelOrientadorView(TipoRequeridoMixin, TemplateView):
    template_name = "empresas/painel_orientador.html"
    tipos_permitidos = (Utilizador.Tipo.ORIENTADOR,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        orientador = (
            Orientador.objects.select_related("empresa")
            .filter(utilizador=self.request.user)
            .first()
        )
        contexto["orientador"] = orientador
        contexto["estagios"] = (
            Candidatura.objects.filter(orientador=orientador, estado=Candidatura.Estado.APROVADO)
            .select_related("vaga", "estudante__utilizador", "estudante__curso")
            .order_by("-atualizado_em")
            if orientador
            else []
        )
        return contexto