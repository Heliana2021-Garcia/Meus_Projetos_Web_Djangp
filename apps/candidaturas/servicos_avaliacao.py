"""Regras da avaliação final: papéis, nota pesada e conclusão do estágio."""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.contas.models import Utilizador
from apps.core.notificacoes import notificar, notificar_gestao

from .models import Avaliacao, Candidatura, RegistoDiario, RelatorioEstagio, pesos_avaliacao


def pesos():
    return pesos_avaliacao()


def papel_do_utilizador(candidatura, utilizador):
    """Papel que o utilizador tem nesta avaliação (ou None se não participa)."""
    if utilizador.pk == candidatura.vaga.empresa.utilizador_id:
        return Avaliacao.Papel.EMPRESA
    if candidatura.orientador_id and candidatura.orientador.utilizador_id == utilizador.pk:
        return Avaliacao.Papel.ORIENTADOR
    if utilizador.pk == candidatura.estudante.utilizador_id:
        return Avaliacao.Papel.ESTUDANTE
    if utilizador.tipo == Utilizador.Tipo.COORDENADOR:
        return Avaliacao.Papel.COORDENADOR
    return None


def faltam(candidatura):
    feitas = set(candidatura.avaliacoes.values_list("papel", flat=True))
    return [papel for papel in pesos() if papel not in feitas]


def nota_final(candidatura):
    """Média pesada das avaliações; None enquanto faltar alguma."""
    if faltam(candidatura):
        return None
    tabela = pesos()
    total = Decimal(sum(tabela.values()))
    soma = sum(
        (a.nota * Decimal(tabela[a.papel]) for a in candidatura.avaliacoes.all() if a.papel in tabela),
        Decimal("0"),
    )
    return (soma / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def impedimentos_conclusao(candidatura):
    if candidatura.estagio_estado != "EM_CURSO":
        return ["O estágio não está em curso."]
    problemas = []
    em_falta = faltam(candidatura)
    if em_falta:
        nomes = ", ".join(Avaliacao.Papel(p).label for p in em_falta)
        problemas.append(f"Faltam as avaliações: {nomes}.")
    if not candidatura.relatorios.filter(
        tipo=RelatorioEstagio.Tipo.FINAL, estado=RelatorioEstagio.Estado.VALIDADO
    ).exists():
        problemas.append("O relatório final ainda não foi validado pelo orientador.")
    pendentes = candidatura.registos.exclude(estado=RegistoDiario.Estado.VALIDADO).count()
    if pendentes:
        problemas.append(f"Existem {pendentes} registos do diário por validar ou corrigir.")
    elif not candidatura.registos.exists():
        problemas.append("O diário de actividades não tem registos.")
    return problemas


def concluir(candidatura, utilizador):
    if utilizador.tipo != Utilizador.Tipo.COORDENADOR:
        raise ValidationError("Só a coordenação pode validar a conclusão do estágio.")

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
        f"com a nota final {atual.avaliacao_final}."
    )
    destinos = [
        (atual.estudante.utilizador, reverse("candidaturas:avaliacao", args=[atual.pk])),
        (atual.vaga.empresa.utilizador, reverse("candidaturas:estagios")),
    ]
    if atual.orientador_id:
        destinos.append((atual.orientador.utilizador, reverse("empresas:painel_orientador")))
    for destino, url in destinos:
        notificar(destino, "Estágio concluído", texto, url)
    candidatura.refresh_from_db()
    return candidatura


def apos_nova_avaliacao(candidatura):
    """Avisa a coordenação quando as avaliações ficam completas."""
    if not faltam(candidatura):
        notificar_gestao(
            "Avaliações completas",
            f"O estágio de {candidatura._nome_estudante} já tem todas as avaliações. "
            "Pode validar a conclusão.",
            reverse("candidaturas:avaliacao", args=[candidatura.pk]),
        )