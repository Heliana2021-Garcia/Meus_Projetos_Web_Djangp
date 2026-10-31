from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.candidaturas.models import Candidatura
from apps.estudantes.models import PerfilEstudante

from .forms import VagaForm
from .mixins import EmpresaRequeridaMixin, EstudanteRequeridoMixin
from .models import Vaga


# ---------------------------------------------------------------- empresa
class MinhasVagasView(EmpresaRequeridaMixin, ListView):
    template_name = "vagas/empresa_lista.html"
    context_object_name = "vagas"

    def get_queryset(self):
        return Vaga.objects.filter(empresa=self.empresa).annotate(
            total_candidaturas=Count("candidaturas")
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["empresa"] = self.empresa
        return contexto


class VagaCreateView(EmpresaRequeridaMixin, CreateView):
    form_class = VagaForm
    template_name = "vagas/vaga_form.html"
    success_url = reverse_lazy("vagas:minhas")
    extra_context = {"titulo_pagina": "Nova vaga"}

    def form_valid(self, form):
        form.instance.empresa = self.empresa
        messages.success(self.request, "Vaga criada como rascunho. Publique-a quando estiver pronta.")
        return super().form_valid(form)


class VagaUpdateView(EmpresaRequeridaMixin, UpdateView):
    form_class = VagaForm
    template_name = "vagas/vaga_form.html"
    success_url = reverse_lazy("vagas:minhas")
    extra_context = {"titulo_pagina": "Editar vaga"}

    def get_queryset(self):
        return Vaga.objects.filter(empresa=self.empresa)

    def form_valid(self, form):
        messages.success(self.request, "Vaga actualizada.")
        return super().form_valid(form)


class PublicarVagaView(EmpresaRequeridaMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        vaga = get_object_or_404(Vaga, pk=pk, empresa=self.empresa)
        try:
            if vaga.estado not in (Vaga.Estado.RASCUNHO, Vaga.Estado.ENCERRADA):
                raise ValidationError("Esta vaga já está publicada ou em análise.")
            if vaga.estado == Vaga.Estado.ENCERRADA:
                vaga.publicar()
            else:
                vaga.submeter()
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
        else:
            if vaga.estado == Vaga.Estado.EM_ANALISE:
                messages.success(request, f"A vaga \"{vaga.titulo}\" foi enviada para aprovação do INSTIC.")
            else:
                messages.success(request, f"A vaga \"{vaga.titulo}\" foi reaberta.")
        return redirect("vagas:minhas")


class EncerrarVagaView(EmpresaRequeridaMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        vaga = get_object_or_404(Vaga, pk=pk, empresa=self.empresa)
        vaga.encerrar()
        messages.success(request, f"A vaga \"{vaga.titulo}\" foi encerrada.")
        return redirect("vagas:minhas")


# --------------------------------------------------------------- estudante
class FeedVagasView(EstudanteRequeridoMixin, ListView):
    template_name = "vagas/feed.html"
    context_object_name = "vagas"
    paginate_by = 8

    def get_queryset(self):
        consulta = (
            Vaga.objects.para_feed()
            .select_related("empresa")
            .prefetch_related("tecnologias", "cursos")
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            consulta = consulta.filter(
                Q(titulo__icontains=q)
                | Q(empresa__nome__icontains=q)
                | Q(tecnologias__nome__icontains=q)
            ).distinct()
        tipo = self.request.GET.get("tipo", "").strip()
        if tipo in Vaga.Tipo.values:
            consulta = consulta.filter(tipo_estagio=tipo)
        area = self.request.GET.get("area", "").strip()
        if area:
            consulta = consulta.filter(area__icontains=area)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        perfil = self.perfil
        minhas = set(perfil.tecnologias.values_list("pk", flat=True))
        candidatadas = set(
            Candidatura.objects.filter(estudante=perfil).values_list("vaga_id", flat=True)
        )

        itens = []
        for vaga in contexto["object_list"]:
            exigidas = {t.pk for t in vaga.tecnologias.all()}
            compatibilidade = (
                100 if not exigidas else round(100 * len(exigidas & minhas) / len(exigidas))
            )
            cursos = {c.pk for c in vaga.cursos.all()}
            itens.append(
                {
                    "vaga": vaga,
                    "compatibilidade": compatibilidade,
                    "ja_candidatou": vaga.pk in candidatadas,
                    "aceita_curso": not cursos or perfil.curso_id in cursos,
                }
            )

        contexto["itens"] = itens
        contexto["perfil"] = perfil
        contexto["q"] = self.request.GET.get("q", "").strip()
        contexto["tipo"] = self.request.GET.get("tipo", "").strip()
        contexto["area"] = self.request.GET.get("area", "").strip()
        contexto["tipos"] = Vaga.Tipo.choices
        return contexto


class VagaDetalheView(EstudanteRequeridoMixin, DetailView):
    template_name = "vagas/detalhe.html"
    context_object_name = "vaga"

    def get_queryset(self):
        return (
            Vaga.objects.publicas()
            .select_related("empresa")
            .prefetch_related("tecnologias", "cursos")
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        vaga = self.object
        perfil = self.perfil

        candidatura = Candidatura.objects.filter(estudante=perfil, vaga=vaga).first()
        aceita_curso = vaga.aceita_curso(perfil.curso)
        motivos = list(perfil.motivos_inelegibilidade)
        ocupado = perfil.estado == PerfilEstudante.Estado.OCUPADO

        contexto.update(
            perfil=perfil,
            candidatura=candidatura,
            aceita_curso=aceita_curso,
            motivos=motivos,
            ocupado=ocupado,
            compatibilidade=vaga.compatibilidade(perfil),
            minhas_tecnologias=set(perfil.tecnologias.values_list("pk", flat=True)),
            pode_candidatar=(
                candidatura is None and aceita_curso and not motivos and not ocupado
            ),
        )
        return contexto


class CandidatarView(EstudanteRequeridoMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        vaga = get_object_or_404(Vaga.objects.publicas(), pk=pk)
        try:
            Candidatura.objects.create(
                estudante=self.perfil,
                vaga=vaga,
                mensagem=request.POST.get("mensagem", "").strip(),
            )
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
            return redirect("vagas:detalhe", pk=vaga.pk)

        messages.success(request, f"Candidatura enviada para \"{vaga.titulo}\".")
        return redirect("candidaturas:minhas")