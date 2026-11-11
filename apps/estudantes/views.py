from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador

from .forms import DocumentosEstudanteForm
from .models import DocumentoEstudante, PerfilEstudante
from .servicos import submeter_documentos


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
        perfil = contexto["perfil"]
        if perfil:
            from apps.candidaturas.models import Candidatura
            from apps.candidaturas.views_estagio import estagio_do_estudante

            contexto["documentos"] = perfil.documentos.all()
            contexto["estagio_actual"] = estagio_do_estudante(perfil)
            if contexto["estagio_actual"] is None:
                ordem = Candidatura.ESTADOS_ATIVOS
                activas = sorted(
                    Candidatura.objects.filter(estudante=perfil, estado__in=ordem)
                    .select_related("vaga__empresa"),
                    key=lambda c: ordem.index(c.estado),
                    reverse=True,
                )
                contexto["candidatura_avancada"] = activas[0] if activas else None
                contexto["total_activas"] = len(activas)
        return contexto


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

    def get(self, request, *args, **kwargs):
        # Os documentos passaram para «Editar o meu perfil».
        return redirect(reverse("contas:editar_perfil") + "#documentos")

    def post(self, request, *args, **kwargs):
        if self.perfil.registo_estado == PerfilEstudante.Registo.APROVADO:
            messages.info(request, "O seu registo já foi aprovado. Os documentos não podem ser alterados.")
            return redirect(self.success_url)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        submeter_documentos(self.perfil, form.cleaned_data)
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
