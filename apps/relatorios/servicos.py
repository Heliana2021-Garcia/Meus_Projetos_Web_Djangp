from django.db.models import Avg, Count, Q

from apps.candidaturas.models import Candidatura
from apps.empresas.models import Empresa
from apps.estudantes.models import Curso, PerfilEstudante
from apps.vagas.models import Vaga

APROVADO = Candidatura.Estado.APROVADO


def _pct(parte, total):
    return round(100 * parte / total) if total else 0


def indicadores_gerais():
    total = PerfilEstudante.objects.count()
    elegiveis = PerfilEstudante.objects.filter(
        ano_frequencia__gte=PerfilEstudante.ANO_MINIMO_CANDIDATURA,
        media_geral__gte=PerfilEstudante.MEDIA_MINIMA_CANDIDATURA,
    ).count()
    colocados = (
        PerfilEstudante.objects.filter(candidaturas__estado=APROVADO).distinct().count()
    )
    em_estagio = PerfilEstudante.objects.filter(
        estado=PerfilEstudante.Estado.OCUPADO
    ).count()

    concluidos = Candidatura.objects.filter(concluida_em__isnull=False)

    return {
        "total_estudantes": total,
        "elegiveis": elegiveis,
        "colocados": colocados,
        "taxa_colocacao": _pct(colocados, total),
        "em_estagio": em_estagio,
        "estagios_concluidos": concluidos.count(),
        "media_avaliacoes": concluidos.aggregate(m=Avg("avaliacao_final"))["m"],
        "total_empresas": Empresa.objects.count(),
        "empresas_parceiras": Empresa.objects.filter(tipo=Empresa.Tipo.PARCEIRA).count(),
        "empresas_nif_pendente": Empresa.objects.filter(nif_validado=False).count(),
        "vagas_abertas": Vaga.objects.filter(estado=Vaga.Estado.ABERTA).count(),
    }


def resumo_por_curso():
    cursos = Curso.objects.annotate(
        total=Count("estudantes", distinct=True),
        colocados=Count(
            "estudantes",
            filter=Q(estudantes__candidaturas__estado=APROVADO),
            distinct=True,
        ),
        media_avaliacao=Avg(
            "estudantes__candidaturas__avaliacao_final",
            filter=Q(estudantes__candidaturas__estado=APROVADO),
        ),
    ).order_by("nome")

    return [
        {
            "curso": c,
            "total": c.total,
            "colocados": c.colocados,
            "taxa": _pct(c.colocados, c.total),
            "media_avaliacao": c.media_avaliacao,
        }
        for c in cursos
    ]


def funil_candidaturas():
    contagem = dict(Candidatura.objects.values_list("estado").annotate(n=Count("id")))
    total = sum(contagem.values())
    return {
        "total": total,
        "etapas": [
            {
                "estado": estado.value,
                "rotulo": estado.label,
                "n": contagem.get(estado.value, 0),
                "pct": _pct(contagem.get(estado.value, 0), total),
            }
            for estado in Candidatura.Estado
        ],
    }


def empresas_com_mais_estagiarios(limite=5):
    return (
        Empresa.objects.annotate(
            estagiarios=Count(
                "vagas__candidaturas",
                filter=Q(vagas__candidaturas__estado=APROVADO),
            ),
            media=Avg(
                "vagas__candidaturas__avaliacao_final",
                filter=Q(vagas__candidaturas__estado=APROVADO),
            ),
        )
        .filter(estagiarios__gt=0)
        .order_by("-estagiarios", "nome")[:limite]
    )