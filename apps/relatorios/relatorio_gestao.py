"""Relatórios de gestão: estudantes, empresas, vagas e candidaturas, com dados reais."""
import csv
from collections import Counter
from datetime import datetime, time, timedelta
from io import StringIO

from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.candidaturas.models import Candidatura
from apps.empresas.models import Empresa
from apps.estudantes.models import Curso, PerfilEstudante
from apps.vagas.models import Vaga

SIM_NAO = [("sim", "Sim"), ("nao", "Não")]


def _texto(valor):
    return "" if valor is None else str(valor)


def _rotulo(obj, campo):
    metodo = getattr(obj, f"get_{campo}_display", None)
    return _texto(metodo() if metodo else getattr(obj, campo, ""))


def _nome(utilizador):
    return utilizador.get_full_name() or utilizador.email or utilizador.username


def _data(valor):
    if not valor:
        return ""
    if isinstance(valor, datetime) and timezone.is_aware(valor):
        valor = timezone.localtime(valor)
    return valor.strftime("%d/%m/%Y")


def _escolhas(modelo, campo):
    """Opções de um campo: as suas escolhas, ou os valores que existem na base."""
    def opcoes():
        campo_modelo = modelo._meta.get_field(campo)
        if campo_modelo.choices:
            return [(str(v), str(r)) for v, r in campo_modelo.choices]
        valores = modelo.objects.values_list(campo, flat=True).distinct().order_by(campo)
        return [(str(v), str(v)) for v in valores if v not in (None, "")]
    return opcoes


def _lista(modelo, rotulo, ordem="pk"):
    return lambda: [(str(o.pk), rotulo(o)) for o in modelo.objects.order_by(ordem)]


def _contagem(modelo, campo):
    return dict(modelo.objects.values_list(campo).annotate(n=Count("id")))


def _curso(estudante):
    curso = getattr(estudante, "curso", None)
    return curso.nome if curso else ""


ENTIDADES = {
    "estudantes": {
        "titulo": "Estudantes",
        "queryset": lambda: PerfilEstudante.objects.select_related("utilizador", "curso"),
        "campo_data": "criado_em",
        "ordem": ("curso__nome", "numero_estudante"),
        "filtros": [
            {"nome": "curso", "rotulo": "Curso", "lookup": "curso_id",
             "opcoes": _lista(Curso, lambda c: f"{c.sigla} - {c.nome}", "nome")},
            {"nome": "estado", "rotulo": "Registo", "lookup": "registo_estado",
             "opcoes": _escolhas(PerfilEstudante, "registo_estado")},
            {"nome": "ano", "rotulo": "Ano de frequência", "lookup": "ano_frequencia",
             "opcoes": _escolhas(PerfilEstudante, "ano_frequencia")},
        ],
        "colunas": [
            ("Nº de estudante", lambda o, e: o.numero_estudante),
            ("Nome", lambda o, e: _nome(o.utilizador)),
            ("Email", lambda o, e: o.utilizador.email),
            ("Curso", lambda o, e: _curso(o)),
            ("Ano", lambda o, e: o.ano_frequencia),
            ("Média", lambda o, e: o.media_geral),
            ("Registo", lambda o, e: _rotulo(o, "registo_estado")),
        ],
        "resumo_titulo": "Por estado do registo",
        "agrupar": lambda o, e: _rotulo(o, "registo_estado"),
    },
    "empresas": {
        "titulo": "Empresas",
        "queryset": lambda: Empresa.objects.select_related("utilizador"),
        "campo_data": "criado_em",
        "ordem": ("nome",),
        "filtros": [
            {"nome": "sector", "rotulo": "Sector", "lookup": "sector",
             "opcoes": _escolhas(Empresa, "sector")},
            {"nome": "nif", "rotulo": "NIF validado", "lookup": "nif_validado",
             "opcoes": lambda: SIM_NAO, "converter": lambda v: v == "sim"},
        ],
        "preparar": lambda: {"vagas": _contagem(Vaga, "empresa_id")},
        "colunas": [
            ("Empresa", lambda o, e: o.nome),
            ("NIF", lambda o, e: o.nif),
            ("Sector", lambda o, e: o.sector),
            ("Tipo", lambda o, e: _rotulo(o, "tipo")),
            ("Telefone", lambda o, e: o.telefone),
            ("NIF validado", lambda o, e: "Sim" if o.nif_validado else "Não"),
            ("Vagas publicadas", lambda o, e: e["vagas"].get(o.pk, 0)),
        ],
        "resumo_titulo": "Por validação do NIF",
        "agrupar": lambda o, e: "NIF validado" if o.nif_validado else "NIF por validar",
    },
    "vagas": {
        "titulo": "Vagas",
        "queryset": lambda: Vaga.objects.select_related("empresa"),
        "campo_data": "criado_em",
        "ordem": ("-criado_em",),
        "filtros": [
            {"nome": "estado", "rotulo": "Estado", "lookup": "estado",
             "opcoes": _escolhas(Vaga, "estado")},
            {"nome": "tipo", "rotulo": "Tipo de estágio", "lookup": "tipo_estagio",
             "opcoes": _escolhas(Vaga, "tipo_estagio")},
            {"nome": "modalidade", "rotulo": "Modalidade", "lookup": "modalidade",
             "opcoes": _escolhas(Vaga, "modalidade")},
            {"nome": "empresa", "rotulo": "Empresa", "lookup": "empresa_id",
             "opcoes": _lista(Empresa, lambda e: e.nome, "nome")},
            {"nome": "curso", "rotulo": "Curso", "lookup": "cursos__id",
             "opcoes": _lista(Curso, lambda c: f"{c.sigla} - {c.nome}", "nome")},
        ],
        "preparar": lambda: {"candidaturas": _contagem(Candidatura, "vaga_id")},
        "colunas": [
            ("Vaga", lambda o, e: o.titulo),
            ("Empresa", lambda o, e: o.empresa.nome),
            ("Área", lambda o, e: _rotulo(o, "area")),
            ("Tipo", lambda o, e: _rotulo(o, "tipo_estagio")),
            ("Modalidade", lambda o, e: _rotulo(o, "modalidade")),
            ("Nº de vagas", lambda o, e: o.numero_vagas),
            ("Data limite", lambda o, e: _data(o.data_limite)),
            ("Estado", lambda o, e: _rotulo(o, "estado")),
            ("Candidaturas", lambda o, e: e["candidaturas"].get(o.pk, 0)),
        ],
        "resumo_titulo": "Por estado da vaga",
        "agrupar": lambda o, e: _rotulo(o, "estado"),
    },
    "candidaturas": {
        "titulo": "Candidaturas",
        "queryset": lambda: Candidatura.objects.select_related(
            "estudante__utilizador", "estudante__curso", "vaga__empresa"),
        "campo_data": "criado_em",
        "ordem": ("-criado_em",),
        "filtros": [
            {"nome": "estado", "rotulo": "Estado", "lookup": "estado",
             "opcoes": _escolhas(Candidatura, "estado")},
            {"nome": "empresa", "rotulo": "Empresa", "lookup": "vaga__empresa_id",
             "opcoes": _lista(Empresa, lambda e: e.nome, "nome")},
            {"nome": "tipo", "rotulo": "Tipo de estágio", "lookup": "vaga__tipo_estagio",
             "opcoes": _escolhas(Vaga, "tipo_estagio")},
            {"nome": "curso", "rotulo": "Curso", "lookup": "estudante__curso_id",
             "opcoes": _lista(Curso, lambda c: f"{c.sigla} - {c.nome}", "nome")},
        ],
        "colunas": [
            ("Estudante", lambda o, e: _nome(o.estudante.utilizador)),
            ("Curso", lambda o, e: _curso(o.estudante)),
            ("Vaga", lambda o, e: o.vaga.titulo),
            ("Empresa", lambda o, e: o.vaga.empresa.nome),
            ("Tipo", lambda o, e: _rotulo(o.vaga, "tipo_estagio")),
            ("Estado", lambda o, e: _rotulo(o, "estado")),
            ("Submetida em", lambda o, e: _data(o.criado_em)),
        ],
        "resumo_titulo": "Por estado da candidatura",
        "agrupar": lambda o, e: _rotulo(o, "estado"),
    },
}


def _data_valida(texto):
    try:
        return parse_date(texto or "")
    except ValueError:
        return None


def _inicio_dia(dia):
    momento = datetime.combine(dia, time.min)
    return timezone.make_aware(momento) if settings.USE_TZ else momento


def gerar(chave, dados):
    """Aplica os filtros recebidos (ignorando valores inválidos) e devolve o relatório."""
    ent = ENTIDADES[chave]
    qs = ent["queryset"]()
    filtros, aplicados = [], []
    for f in ent["filtros"]:
        opcoes = f["opcoes"]()
        valor = dados.get(f["nome"], "")
        if valor not in {v for v, _ in opcoes}:
            valor = ""
        if valor:
            converter = f.get("converter", lambda v: v)
            qs = qs.filter(**{f["lookup"]: converter(valor)})
            aplicados.append(f"{f['rotulo']}: {dict(opcoes)[valor]}")
        filtros.append({"nome": f["nome"], "rotulo": f["rotulo"], "opcoes": opcoes, "valor": valor})

    de = _data_valida(dados.get("de"))
    ate = _data_valida(dados.get("ate"))
    campo = ent["campo_data"]
    if de:
        qs = qs.filter(**{f"{campo}__gte": _inicio_dia(de)})
        aplicados.append(f"De: {_data(de)}")
    if ate:
        qs = qs.filter(**{f"{campo}__lt": _inicio_dia(ate + timedelta(days=1))})
        aplicados.append(f"Até: {_data(ate)}")

    objectos = list(qs.distinct().order_by(*ent["ordem"]))
    extra = ent["preparar"]() if "preparar" in ent else {}
    linhas = [[_texto(coluna(o, extra)) for _, coluna in ent["colunas"]] for o in objectos]
    contagem = Counter(ent["agrupar"](o, extra) for o in objectos)
    return {
        "titulo": ent["titulo"],
        "colunas": [rotulo for rotulo, _ in ent["colunas"]],
        "linhas": linhas,
        "total": len(linhas),
        "resumo_titulo": ent["resumo_titulo"],
        "resumo": sorted(contagem.items(), key=lambda p: (-p[1], p[0])),
        "filtros": filtros,
        "aplicados": aplicados,
        "de": de.isoformat() if de else "",
        "ate": ate.isoformat() if ate else "",
    }


def _celula_segura(texto):
    # Evita que o Excel interprete uma célula como fórmula.
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def para_csv(relatorio):
    saida = StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow(relatorio["colunas"])
    for linha in relatorio["linhas"]:
        escritor.writerow([_celula_segura(c) for c in linha])
    return "\ufeff" + saida.getvalue()