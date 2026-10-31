"""Filtros do relatório de estágios (partilhados pelo ecrã, CSV e PDF)."""
from collections import Counter

from django.db.models import Q
from django.utils.dateparse import parse_date

from apps.candidaturas.models import Candidatura
from apps.vagas.models import Vaga

ESTADOS = (
    ("POR_INICIAR", "Por iniciar"),
    ("EM_CURSO", "Em curso"),
    ("INTERROMPIDO", "Interrompido"),
    ("CONCLUIDO", "Concluído"),
)


def modelo_curso():
    perfil = Candidatura._meta.get_field("estudante").related_model
    return perfil._meta.get_field("curso").related_model


def cursos():
    return modelo_curso().objects.order_by("sigla")


def tipos():
    return Vaga._meta.get_field("tipo_estagio").choices


def _q_estado(estado):
    interrompido = Q(interrompido_em__isnull=False)
    concluido = Q(concluida_em__isnull=False, interrompido_em__isnull=True)
    em_curso = Q(
        inicio_confirmado_empresa__isnull=False, inicio_confirmado_estudante__isnull=False,
        interrompido_em__isnull=True, concluida_em__isnull=True,
    )
    if estado == "INTERROMPIDO":
        return interrompido
    if estado == "CONCLUIDO":
        return concluido
    if estado == "EM_CURSO":
        return em_curso
    return ~(interrompido | concluido | em_curso)


def _data(valor):
    try:
        return parse_date(valor or "")
    except ValueError:
        return None


def filtrar(params):
    qs = (
        Candidatura.objects.filter(estado=Candidatura.Estado.APROVADO)
        .select_related("vaga__empresa", "estudante__utilizador", "estudante__curso", "orientador__utilizador")
        .order_by("-atualizado_em")
    )
    curso = params.get("curso", "")
    if curso.isdigit():
        qs = qs.filter(estudante__curso_id=int(curso))
    empresa = params.get("empresa", "").strip()
    if empresa:
        qs = qs.filter(vaga__empresa__nome__icontains=empresa)
    tipo = params.get("tipo", "")
    if tipo in dict(tipos()):
        qs = qs.filter(vaga__tipo_estagio=tipo)
    estado = params.get("estado", "")
    if estado in dict(ESTADOS):
        qs = qs.filter(_q_estado(estado))
    de = _data(params.get("de"))
    if de:
        qs = qs.filter(data_inicio__gte=de)
    ate = _data(params.get("ate"))
    if ate:
        qs = qs.filter(data_inicio__lte=ate)
    return qs


def totais(linhas):
    contagem = Counter(c.estagio_estado for c in linhas)
    notas = [
        c.avaliacao_final for c in linhas
        if c.estagio_estado == "CONCLUIDO" and c.avaliacao_final is not None
    ]
    media = round(sum(notas) / len(notas), 2) if notas else None
    return contagem, media


def descrever(params):
    """Texto dos filtros aplicados, para o cabeçalho do PDF."""
    partes = []
    curso = params.get("curso", "")
    if curso.isdigit():
        obj = modelo_curso().objects.filter(pk=int(curso)).first()
        if obj:
            partes.append(f"Curso: {obj.sigla}")
    if params.get("empresa", "").strip():
        partes.append(f"Empresa: {params['empresa'].strip()}")
    tipo = params.get("tipo", "")
    if tipo in dict(tipos()):
        partes.append(f"Modalidade: {dict(tipos())[tipo]}")
    estado = params.get("estado", "")
    if estado in dict(ESTADOS):
        partes.append(f"Estado: {dict(ESTADOS)[estado]}")
    de, ate = _data(params.get("de")), _data(params.get("ate"))
    if de:
        partes.append(f"Início a partir de {de:%d/%m/%Y}")
    if ate:
        partes.append(f"Início até {ate:%d/%m/%Y}")
    return partes