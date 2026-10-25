import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django
django.setup()

from apps.estudantes.models import Curso

CURSOS = [
    ("Engenharia Inform\u00e1tica", "EI"),
    ("Engenharia de Telecomunica\u00e7\u00f5es", "ET"),
    ("Inform\u00e1tica de Gest\u00e3o", "IG"),
]

for nome, sigla in CURSOS:
    Curso.objects.get_or_create(sigla=sigla, defaults={"nome": nome})

print(Curso.objects.count(), "cursos")
