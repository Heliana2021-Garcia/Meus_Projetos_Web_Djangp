from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView, UpdateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador

from .forms import PerfilEstudanteForm
from .models import PerfilEstudante


class PainelEstudanteView(TipoRequeridoMixin, TemplateView):
    template_name = "estudantes/painel.html"
    tipos_permitidos = (Utilizador.Tipo.ESTUDANTE,)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["perfil"] = (
            PerfilEstudante.objects.select_related("curso")
            .filter(utilizador=self.request.user)
            .first()
        )
        return contexto


class PerfilEstudanteUpdateView(TipoRequeridoMixin, UpdateView):
    template_name = "estudantes/perfil_form.html"
    tipos_permitidos = (Utilizador.Tipo.ESTUDANTE,)
    form_class = PerfilEstudanteForm
    success_url = reverse_lazy("estudantes:painel")

    def get_object(self, queryset=None):
        return get_object_or_404(PerfilEstudante, utilizador=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Perfil actualizado.")
        return super().form_valid(form)