"""Regras da avaliacao e da conclusao do estagio.

- O orientador atribui uma nota (0 a 20) a cada registo do diario; a nota final e a media.
- O estudante avalia o orientador de 30 em 30 dias; so a empresa ve essas avaliacoes.
- A empresa de acolhimento aprova a conclusao depois da data de fim prevista.
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.contas.models import Utilizador
from apps.core.notificacoes import notificar, notificar_gestao

from .models import Candidatura, RegistoDiario, RelatorioEstagio

DIAS_POR_PERIODO = 30
EMPRESA = "EMPRESA"
ORIENTADOR = "ORIENTADOR"
ESTUDANTE = "ESTUDANTE"
COORDENADOR = "COORDENADOR"


def papel_do_utilizador(candidatura, utilizador):
    """Papel do utilizador neste estagio (ou None se nao participa)."""
    if utilizador.pk == candidatura.vaga.empresa.utilizador_id:
        return EMPRESA
    if candidatura.orientador_id and candidatura.orientador.utilizador_id == utilizador.pk:
        return ORIENTADOR
    if utilizador.pk == candidatura.estudante.utilizador_id:
        return ESTUDANTE
    if utilizador.tipo == Utilizador.Tipo.COORDENADOR:
        return COORDENADOR
    return None


# ---------------------------------------------------- avaliacao mensal do orientador
def total_avaliacoes_mensais(candidatura):
    return candidatura.vaga.duracao_meses


def abertura_do_mes(candidatura, mes):
    """Data a partir da qual o estudante pode avaliar o orientador no mes indicado.

    A ultima abre, no maximo, na data de fim (evita bloquear estagios que atravessam fevereiro)."""
    abre = candidatura.data_inicio + timedelta(days=DIAS_POR_PERIODO * mes)
    if mes >= total_avaliacoes_mensais(candidatura) and candidatura.data_fim:
        abre = min(abre, candidatura.data_fim)
    return abre


def estado_mensal(candidatura):
    if not candidatura.data_inicio:
        return []
    feitas = {a.mes: a for a in candidatura.avaliacoes_mensais.all()}
    hoje = timezone.localdate()
    linhas = []
    for mes in range(1, total_avaliacoes_mensais(candidatura) + 1):
        abre = abertura_do_mes(candidatura, mes)
        linhas.append({"mes": mes, "abre_em": abre, "aberta": hoje >= abre, "avaliacao": feitas.get(mes)})
    return linhas


def proximo_mes(candidatura):
    """Primeiro mes por avaliar, se ja estiver aberto; caso contrario None (segue a ordem dos meses)."""
    for linha in estado_mensal(candidatura):
        if linha["avaliacao"] is None:
            return linha["mes"] if linha["aberta"] else None
    return None


def avaliacoes_mensais_em_falta(candidatura):
    return sum(1 for linha in estado_mensal(candidatura) if linha["avaliacao"] is None)


# ------------------------------------------------------------------ nota e conclusao
def nota_final(candidatura):
    """Media das notas que o orientador deu aos registos validados; None se ainda nao ha notas."""
    notas = list(
        candidatura.registos.filter(
            estado=RegistoDiario.Estado.VALIDADO, nota__isnull=False
        ).values_list("nota", flat=True)
    )
    if not notas:
        return None
    return (sum(notas, Decimal("0")) / len(notas)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def impedimentos_conclusao(candidatura):
    if candidatura.estagio_estado != "EM_CURSO":
        return ["O estágio não está em curso."]
    problemas = []
    if candidatura.data_fim and timezone.localdate() < candidatura.data_fim:
        problemas.append(
            "O estágio só pode ser concluído depois da data de fim prevista "
            f"({candidatura.data_fim:%d/%m/%Y})."
        )
    if not candidatura.registos.exists():
        problemas.append("O diário de actividades não tem registos.")
    else:
        pendentes = candidatura.registos.exclude(estado=RegistoDiario.Estado.VALIDADO).count()
        if pendentes:
            problemas.append(
                f"Existem {pendentes} registos do diário por avaliar ou corrigir pelo orientador."
            )
        elif nota_final(candidatura) is None:
            problemas.append("Nenhum registo do diário tem nota do orientador.")
    if not candidatura.relatorios.filter(
        tipo=RelatorioEstagio.Tipo.FINAL, estado=RelatorioEstagio.Estado.VALIDADO
    ).exists():
        problemas.append("O relatório final ainda não foi validado pelo orientador.")
    em_falta = avaliacoes_mensais_em_falta(candidatura)
    if em_falta:
        problemas.append(f"Faltam {em_falta} avaliações mensais do estudante ao orientador.")
    return problemas


def concluir(candidatura, utilizador):
    if utilizador.pk != candidatura.vaga.empresa.utilizador_id:
        raise ValidationError("Só a empresa de acolhimento pode aprovar a conclusão do estágio.")

    with transaction.atomic():
        atual = Candidatura.objects.select_for_update().get(pk=candidatura.pk)
        problemas = impedimentos_conclusao(atual)
        if problemas:
            raise ValidationError(problemas)
        atual.avaliacao_final = nota_final(atual)
        atual.concluida_em = timezone.now()
        atual.save(update_fields=["avaliacao_final", "concluida_em", "atualizado_em"])
        atual.estudante.marcar_disponivel()

    texto = (
        f"O estágio de {atual._nome_estudante} em \"{atual.vaga.titulo}\" foi concluído "
        f"com a nota final {atual.avaliacao_final}/20."
    )
    url = reverse("candidaturas:avaliacao", args=[atual.pk])
    destinos = [(atual.estudante.utilizador, url)]
    if atual.orientador_id:
        destinos.append((atual.orientador.utilizador, reverse("empresas:painel_orientador")))
    for destino, destino_url in destinos:
        notificar(destino, "Estágio concluído", texto, destino_url)
    notificar_gestao("Estágio concluído", texto, url)
    candidatura.refresh_from_db()
    return candidatura


def avisar_se_pronto(candidatura):
    """Avisa a empresa quando ja nao falta nada para aprovar a conclusao."""
    c = Candidatura.objects.select_related("vaga__empresa__utilizador", "estudante__utilizador").get(
        pk=candidatura.pk
    )
    if not impedimentos_conclusao(c):
        notificar(
            c.vaga.empresa.utilizador,
            "Estágio pronto para concluir",
            f"O estágio de {c._nome_estudante} cumpre todas as condições. Pode aprovar a conclusão.",
            reverse("candidaturas:avaliacao", args=[c.pk]),
        )


def apos_avaliacao_mensal(candidatura, avaliacao):
    notificar(
        candidatura.vaga.empresa.utilizador,
        "Nova avaliação do orientador",
        f"{candidatura._nome_estudante} enviou a avaliação do mês {avaliacao.mes} do orientador.",
        reverse("candidaturas:avaliacao", args=[candidatura.pk]),
    )
    avisar_se_pronto(candidatura)
