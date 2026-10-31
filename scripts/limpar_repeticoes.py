import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
S, M = re.S, re.M

REGRAS = {
    "apps/vagas/forms.py": [
        (r'(^[ ]*"documentos_exigidos": forms\.Textarea\(attrs=\{"rows": 3\}\),\n)(?:\1)+', M),
    ],
    "apps/vagas/views.py": [
        (r'(        tipo = self\.request\.GET\.get\("tipo", ""\)\.strip\(\)\n.*?area__icontains=area\)\n)(?:\1)+', S),
        (r'(        contexto\["tipo"\] = [^\n]*\n        contexto\["area"\] = [^\n]*\n        contexto\["tipos"\] = [^\n]*\n)(?:\1)+', 0),
    ],
    "apps/vagas/models.py": [
        (r'(    class Tipo\(models\.TextChoices\):\n.*?help_text="Fase de selecção\."\n    \)\n\n)(?:\1)+', S),
        (r'(    ESTADOS_PROCESSO = \(.*?return fases \+ \["Decisão final"\]\n)(?:\n+\1)+', S),
    ],
    "apps/candidaturas/models.py": [
        (r'(        CURRICULO = "CURRICULO", "Análise do currículo"\n)(?:\1)+', 0),
        (r'(self\.Estado\.CURRICULO: \(\n.*?\n            \),\n            )(?:\1)+', S),
        (r'(    def sequencia\(self\):.*?        return etapas\n)(?:\n+\1)+', S),
    ],
    "apps/candidaturas/tests.py": [
        (r'(from decimal import Decimal  # noqa: E402\n.*?self\.assertEqual\(c\.etapas, \[\]\)\n)(?:\n+\1)+', S),
    ],
    "templates/vagas/feed.html": [
        (r'(  <div class="col-6 col-md-4 col-lg-3">\n    <select name="tipo".*?</select>\n  </div>\n  <div class="col-6 col-md-4 col-lg-3">\n    <input type="search" name="area"[^\n]*\n  </div>\n)(?:\1)+', S),
    ],
    "templates/vagas/detalhe.html": [
        (r'(<dt class="col-sm-3 text-secondary fw-normal">Tipo de estágio</dt>[^\n]*\n[ ]*\{% if vaga\.area %\}[^\n]*\n[ ]*)(?:\1)+', 0),
        (r'(\{% if vaga\.documentos_exigidos %\}[^\n]*\n[ ]*<h2 class="h6 mt-3">Processo de selecção</h2>\n[ ]*<p class="text-secondary mb-0">[^\n]*</p>\n\n[ ]*)(?:\1)+', 0),
    ],
    "templates/candidaturas/minhas.html": [
        (r'(\{% if c\.etapas %\}.*?</ol>\n[ ]*\{% endif %\}\n[ ]*)(?:\1)+', S),
    ],
    "static/css/sigest.css": [
        (r'(/\* Etapas da candidatura \*/\n.*?\.sigest-etapas li\.atual span \{[^\n]*\n)(?:\n+\1)+', S),
    ],
}

for caminho, regras in REGRAS.items():
    ficheiro = RAIZ / caminho
    if not ficheiro.exists():
        print("não existe  |", caminho)
        continue
    texto = ficheiro.read_text(encoding="utf-8-sig")
    original = texto
    removidos = 0
    for padrao, flags in regras:
        texto, n = re.subn(padrao, r"\1", texto, flags=flags)
        removidos += n
    if texto != original:
        ficheiro.write_text(texto, encoding="utf-8", newline="\n")
    print(f"{removidos} repetição(ões) removida(s) | {caminho}")