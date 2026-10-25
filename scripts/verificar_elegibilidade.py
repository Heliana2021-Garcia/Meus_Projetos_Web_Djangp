import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django
django.setup()

from apps.estudantes.models import PerfilEstudante

for p in PerfilEstudante.objects.all():
    print(p, "| elegivel:", p.elegivel, "|", p.motivos_inelegibilidade)
