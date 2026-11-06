import csv
from io import StringIO

from django.utils import timezone

DEPARTAMENTO = "Coordenação de Estágios"
VERSAO = "1.0"
COLUNAS = ["N.º", "Nome Completo", "Curso / Área", "Contacto", "E-mail", "Observações"]


def seguro(valor):
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


def telefone(estudante):
    return getattr(estudante, "telefone", "") or getattr(estudante.utilizador, "telefone", "") or ""


def observacoes(*partes):
    return " | ".join(str(p) for p in partes if p not in (None, ""))


def nome_responsavel(utilizador):
    if not utilizador:
        return ""
    return utilizador.get_full_name() or utilizador.email or utilizador.username


def metadados(responsavel=None, agora=None, periodo="Todos os registos", filtros=()):
    agora = agora or timezone.localtime()
    return {
        "departamento": DEPARTAMENTO,
        "periodo": periodo,
        "responsavel": nome_responsavel(responsavel),
        "versao": VERSAO,
        "data": agora.strftime("%d/%m/%Y"),
        "colunas": COLUNAS,
        "filtros": [f for f in filtros if f],
    }


def csv_registo(titulo, registos, responsavel=None, agora=None, periodo="Todos os registos", filtros=()):
    meta = metadados(responsavel, agora, periodo, filtros)
    saida = StringIO()
    e = csv.writer(saida, delimiter=";")
    linha = lambda *c: e.writerow([seguro(x) for x in c])
    linha("UNIVERSIDADE DE LUANDA")
    linha("Instituto de Tecnologias de Informação e Comunicação (INSTIC)")
    linha("REGISTO DE DADOS - " + titulo.upper())
    linha()
    linha("Departamento", meta["departamento"])
    linha("Período", meta["periodo"])
    linha("Responsável", meta["responsavel"])
    linha("Versão", meta["versao"])
    linha("Data de Elaboração", meta["data"])
    if meta["filtros"]:
        linha("Filtros aplicados", " | ".join(meta["filtros"]))
    linha()
    linha(*COLUNAS)
    for n, registo in enumerate(registos, start=1):
        linha(n, *registo)
    linha()
    linha("Total de Registos", len(registos))
    linha("Data de Actualização", meta["data"])
    return "\ufeff" + saida.getvalue()
