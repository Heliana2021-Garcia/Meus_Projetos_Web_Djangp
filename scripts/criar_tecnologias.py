import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django
django.setup()

from apps.core.models import Tecnologia

TECNOLOGIAS = [
    "Python", "Django", "JavaScript", "HTML/CSS", "SQL", "PostgreSQL", "Java", "C#",
    "PHP", "Laravel", "React", "Git", "Linux", "Redes de computadores", "Cisco",
    "Windows Server", "Cibersegurança", "Excel avançado", "Power BI",
    "Análise de dados", "Gestão de projectos", "Suporte técnico",
]

for nome in TECNOLOGIAS:
    Tecnologia.objects.get_or_create(nome=nome)

print(Tecnologia.objects.count(), "tecnologias")