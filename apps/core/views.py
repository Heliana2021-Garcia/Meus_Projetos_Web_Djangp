from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from .models import Notificacao


class ListaNotificacoesView(LoginRequiredMixin, ListView):
    template_name = "core/notificacoes.html"
    context_object_name = "notificacoes"
    paginate_by = 15

    def get_queryset(self):
        return Notificacao.objects.filter(destinatario=self.request.user)


class AbrirNotificacaoView(LoginRequiredMixin, View):
    def get(self, request, pk):
        notificacao = get_object_or_404(Notificacao, pk=pk, destinatario=request.user)
        if not notificacao.lida:
            notificacao.lida = True
            notificacao.save(update_fields=["lida", "atualizado_em"])
        url = notificacao.url
        if url.startswith("/") and not url.startswith("//"):
            return redirect(url)
        return redirect("core:notificacoes")


class MarcarTodasLidasView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        Notificacao.objects.filter(destinatario=request.user, lida=False).update(
            lida=True, atualizado_em=timezone.now()
        )
        return redirect("core:notificacoes")