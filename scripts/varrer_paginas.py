import logging

logging.disable(logging.CRITICAL)
from django.test import Client
from django.urls import URLResolver, get_resolver

SENHA = "Demo#2026"
PERFIS = [
    ("anonimo", None),
    ("coordenador", "demo_coord@demo.ao"),
    ("estudante", "demo_estudante@demo.ao"),
    ("empresa", "demo_empresa@demo.ao"),
    ("orientador", "orientador@demo.ao"),
]


def listar(padroes, prefixo=""):
    for p in padroes:
        if isinstance(p, URLResolver):
            yield from listar(p.url_patterns, prefixo + str(p.pattern))
        else:
            yield prefixo + str(p.pattern), p.name


rotas = sorted({
    "/" + r for r, _ in listar(get_resolver().url_patterns)
    if not any(c in r for c in "<(^$") and not r.startswith(("admin", "media", "static", "sair"))
})

problemas = 0
for nome, email in PERFIS:
    c = Client(raise_request_exception=False, HTTP_HOST="localhost")
    if email and not c.login(username=email, password=SENHA):
        print(f"[{nome}] sem conta ou palavra-passe - ignorado")
        continue
    contagem = {}
    for rota in rotas:
        estado = c.get(rota).status_code
        contagem[estado] = contagem.get(estado, 0) + 1
        if estado >= 500:
            problemas += 1
            print(f"  ERRO {estado}  [{nome}]  {rota}")
    print(f"[{nome}] {len(rotas)} paginas: {dict(sorted(contagem.items()))}")

print("SEM ERROS 500" if not problemas else f"{problemas} pagina(s) com erro 500")


print("\nPAGINA POR PERFIL (anonimo / coord / estudante / empresa)")
clientes = []
for _, email in PERFIS[:4]:
    cl = Client(raise_request_exception=False, HTTP_HOST="localhost")
    if email:
        cl.login(username=email, password=SENHA)
    clientes.append(cl)
for rota in rotas:
    print(f"  {rota:<42}", *[str(cl.get(rota).status_code) for cl in clientes])

print("\nPAGINAS COM PARAMETROS (nao varridas):")
for r, n in sorted(set(listar(get_resolver().url_patterns))):
    if any(c in r for c in "<(") and not r.startswith(("admin", "media", "static")):
        print(f"  /{r}  [{n}]")
