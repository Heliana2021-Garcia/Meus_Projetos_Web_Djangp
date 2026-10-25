from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.candidaturas.models import Candidatura
from apps.contas.mixins import TipoRequeridoMixin
from apps.contas.models import Utilizador

from .models import CartaEncaminhamento
from .pdf import gerar_pdf


class EmitirCartaView(TipoRequeridoMixin, View):
    tipos_permitidos = (Utilizador.Tipo.ADMINISTRADOR,)
    http_method_names = ["post"]

    def post(self, request, pk):
        candidatura = get_object_or_404(
            Candidatura.objects.select_related("estudante__utilizador"), pk=pk
        )
        try:
            carta, criada = CartaEncaminhamento.emitir(candidatura, request.user)
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            if criada:
                messages.success(request, f"Carta emitida: ofício n.º {carta.referencia}.")
            else:
                messages.info(request, f"Esta candidatura já tem a carta {carta.referencia}.")
        return redirect("relatorios:painel")


class DescarregarCartaView(LoginRequiredMixin, View):
    """Administração, estudante da candidatura e empresa da vaga."""

    def _pode_ver(self, utilizador, carta):
        if utilizador.tipo == Utilizador.Tipo.ADMINISTRADOR:
            return True
        candidatura = carta.candidatura
        if utilizador.tipo == Utilizador.Tipo.ESTUDANTE:
            return candidatura.estudante.utilizador_id == utilizador.pk
        if utilizador.tipo == Utilizador.Tipo.EMPRESA:
            return candidatura.vaga.empresa.utilizador_id == utilizador.pk
        return False

    def get(self, request, pk):
        carta = get_object_or_404(
            CartaEncaminhamento.objects.select_related(
                "candidatura__estudante__utilizador",
                "candidatura__estudante__curso",
                "candidatura__vaga__empresa__utilizador",
            ),
            pk=pk,
        )
        if not self._pode_ver(request.user, carta):
            raise PermissionDenied

        resposta = HttpResponse(gerar_pdf(carta), content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="{carta.nome_ficheiro}"'
        return resposta