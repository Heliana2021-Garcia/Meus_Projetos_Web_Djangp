import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django

django.setup()

from django.template.loader import get_template

pasta = RAIZ / "templates"
erros = 0
for ficheiro in sorted(pasta.rglob("*.html")):
    nome = ficheiro.relative_to(pasta).as_posix()
    try:
        get_template(nome)
    except Exception as erro:
        erros += 1
        print("ERRO |", nome, "->", erro)

print("Templates com erro:", erros)