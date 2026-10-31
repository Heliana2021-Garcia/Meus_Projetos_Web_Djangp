from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView, UpdateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador
from apps.core.notificacoes import notificar_gestao

from .forms import DocumentosEstudanteForm, PerfilEstudanteForm
from .models import DocumentoEstudante, PerfilEstudante


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

class DocumentosEstudanteView(TipoRequeridoMixin, FormView):
    template_name = "estudantes/documentos.html"
    tipos_permitidos = (Utilizador.Tipo.ESTUDANTE,)
    form_class = DocumentosEstudanteForm
    success_url = reverse_lazy("estudantes:documentos")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.perfil = get_object_or_404(PerfilEstudante, utilizador=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["perfil"] = self.perfil
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["perfil"] = self.perfil
        contexto["documentos"] = self.perfil.documentos.all()
        contexto["pode_enviar"] = self.perfil.registo_estado != PerfilEstudante.Registo.APROVADO
        return contexto

    def post(self, request, *args, **kwargs):
        if self.perfil.registo_estado == PerfilEstudante.Registo.APROVADO:
            messages.info(request, "O seu registo já foi aprovado. Os documentos não podem ser alterados.")
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        dados = form.cleaned_data
        if dados.get("declaracao_notas"):
            self.perfil.guardar_documento(DocumentoEstudante.Tipo.DECLARACAO, dados["declaracao_notas"])
        if dados.get("bilhete_identidade"):
            self.perfil.guardar_documento(DocumentoEstudante.Tipo.BI, dados["bilhete_identidade"])
        if self.perfil.registo_estado == PerfilEstudante.Registo.DEVOLVIDO:
            self.perfil.resubmeter_registo()
            notificar_gestao(
                "Registo corrigido",
                f"{self.perfil.utilizador} voltou a submeter os documentos para validação.",
                reverse_lazy("relatorios:estudantes_pendentes"),
            )
        messages.success(self.request, "Documentos enviados. A coordenação vai analisá-los.")
        return super().form_valid(form)


class DescarregarDocumentoView(TipoRequeridoMixin, View):
    """Só o próprio estudante e a gestão abrem um documento."""

    tipos_permitidos = (
        Utilizador.Tipo.ESTUDANTE, Utilizador.Tipo.COORDENADOR, Utilizador.Tipo.ADMINISTRADOR,
    )

    def get(self, request, pk):
        documento = get_object_or_404(DocumentoEstudante.objects.select_related("estudante"), pk=pk)
        if request.user.tipo == Utilizador.Tipo.ESTUDANTE and documento.estudante.utilizador_id != request.user.pk:
            raise PermissionDenied
        resposta = FileResponse(documento.ficheiro.open("rb"))
        resposta["X-Content-Type-Options"] = "nosniff"
        return resposta
