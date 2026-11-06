"""Filtros que apresentam o registo de decisoes em linguagem legivel.
Os dados guardados nao sao alterados: so a forma como se mostram."""
import re

from django import template

register = template.Library()

ROTULOS = {
    "motivo": "Motivo",
    "comentario": "Comentário",
    "feedback": "Feedback",
    "resultado": "Resultado",
    "estado": "Estado",
    "fase": "Fase",
    "destino": "Destino",
    "nota": "Nota",
}
ACOES = {
    "validar": "validado",
    "corrigir": "devolvido para correcção",
    "devolver": "devolvido para correcção",
    "rejeitar": "rejeitado",
    "aprovar": "aprovado",
}
SUJEITOS = {"registo": "Registo diário", "relatorio": "Relatório"}
CAMPOS = re.compile(
    r"(?:^|; )(motivo|comentario|acao|feedback|resultado|estado|fase|destino|novo_estado|orientador|nota): "
)


def _campos(detalhe):
    detalhe = detalhe or ""
    encontrados = list(CAMPOS.finditer(detalhe))
    resultado = {}
    for i, m in enumerate(encontrados):
        fim = encontrados[i + 1].start() if i + 1 < len(encontrados) else len(detalhe)
        resultado[m.group(1)] = detalhe[m.end():fim].strip()
    return resultado


def _referencia(ref):
    nome, _, resto = (ref or "").partition(" ")
    args = dict(p.split("=", 1) for p in resto.split(", ") if "=" in p)
    return nome, args


def _obter(modelo, pk, *relacoes):
    qs = modelo.objects
    if relacoes:
        qs = qs.select_related(*relacoes)
    try:
        return qs.get(pk=pk)
    except (modelo.DoesNotExist, ValueError, TypeError):
        return None


def _nome(utilizador):
    return utilizador.get_full_name() or utilizador.username


def _texto_candidatura(c):
    return f"{_nome(c.estudante.utilizador)} · {c.vaga.titulo} · {c.vaga.empresa.nome}"


def _rotulo_estado(codigo):
    from apps.candidaturas.models import Candidatura

    try:
        return Candidatura.Estado(codigo).label
    except ValueError:
        return codigo


@register.filter
def accao_legivel(d):
    nome, args = _referencia(d.referencia)
    campos = _campos(d.detalhe)
    if nome == "candidaturas:decidir":
        verbo = ACOES.get(campos.get("acao", ""))
        if verbo:
            return f"{SUJEITOS.get(args.get('tipo'), 'Registo ou relatório')} {verbo}"
    if nome == "candidaturas:mover" and campos.get("novo_estado"):
        novo = campos["novo_estado"]
        if novo == "REJEITADO":
            return "Candidatura rejeitada"
        if novo == "APROVADO":
            return "Candidatura aprovada pela empresa"
        return f"Candidatura passou a: {_rotulo_estado(novo)}"
    if nome == "relatorios:aprovar_vaga":
        return "Vaga aprovada"
    if nome == "relatorios:devolver_vaga":
        return "Vaga devolvida para correcção"
    return d.accao


@register.filter
def assunto_legivel(d):
    """Sobre quem/o quê foi a decisão (estudante, vaga, empresa)."""
    from apps.candidaturas.models import Candidatura, RegistoDiario, RelatorioEstagio
    from apps.empresas.models import Empresa
    from apps.estudantes.models import PerfilEstudante
    from apps.vagas.models import Vaga

    nome, args = _referencia(d.referencia)
    pk = args.get("pk")
    if not pk:
        return ""
    cand_rel = ("estudante__utilizador", "vaga__empresa")

    if nome == "candidaturas:decidir":
        tipo = args.get("tipo")
        rel = tuple("candidatura__" + r for r in cand_rel)
        if tipo == "registo":
            item = _obter(RegistoDiario, pk, *rel)
            extra = f"registo de {item.data:%d/%m/%Y}" if item else ""
        else:
            item = _obter(RelatorioEstagio, pk, *rel)
            extra = item.get_tipo_display().lower() if item else ""
        if item:
            return f"{_texto_candidatura(item.candidatura)} · {extra}"
        return f"{SUJEITOS.get(tipo, 'Item')} n.º {pk} (já não existe)"

    if nome.endswith("_vaga"):
        v = _obter(Vaga, pk, "empresa")
        return f"{v.titulo} · {v.empresa.nome}" if v else f"Vaga n.º {pk} (já não existe)"
    if nome.endswith("_estudante"):
        p = _obter(PerfilEstudante, pk, "utilizador", "curso")
        if p:
            return f"{_nome(p.utilizador)} · n.º {p.numero_estudante} · {p.curso.sigla}"
        return f"Estudante n.º {pk} (já não existe)"
    if nome == "relatorios:validar_nif":
        e = _obter(Empresa, pk)
        return f"{e.nome} (NIF {e.nif})" if e else f"Empresa n.º {pk} (já não existe)"
    if nome.startswith("candidaturas:"):
        c = _obter(Candidatura, pk, *cand_rel)
        return _texto_candidatura(c) if c else f"Candidatura n.º {pk} (já não existe)"
    return d.referencia


def _orientador(valor):
    from apps.empresas.models import Orientador

    o = _obter(Orientador, valor, "utilizador", "empresa")
    return f"{_nome(o.utilizador)} ({o.empresa.nome})" if o else f"n.º {valor}"


@register.filter
def detalhe_legivel(d):
    from apps.candidaturas.models import Candidatura

    nome, args = _referencia(d.referencia)
    originais = _campos(d.detalhe)
    if not originais and nome != "candidaturas:validar_conclusao":
        return d.detalhe or ""
    campos = dict(originais)
    partes = []

    if nome in ("candidaturas:avaliar", "candidaturas:avaliar_orientador"):
        campos.pop("comentario", None)  # o texto das avaliacoes nao pertence ao historico
    if nome == "candidaturas:validar_conclusao":
        c = _obter(Candidatura, args.get("pk"))
        if c and c.avaliacao_final is not None:
            partes.append(f"Nota final: {c.avaliacao_final}/20")

    for campo, valor in campos.items():
        if campo == "acao":
            if nome == "candidaturas:decidir" and valor in ACOES:
                continue
            partes.append(ACOES.get(valor, valor).capitalize())
        elif campo == "novo_estado":
            continue
        elif campo == "orientador":
            partes.append("Orientador: " + _orientador(valor))
        else:
            partes.append(f"{ROTULOS[campo]}: {valor}")
    return "; ".join(partes)
