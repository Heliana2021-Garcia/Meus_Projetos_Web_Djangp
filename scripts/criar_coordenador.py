import getpass
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django

django.setup()

from django.contrib.auth import get_user_model

Utilizador = get_user_model()

username = input("Nome de utilizador: ").strip()
email = input("Email: ").strip()
nome = input("Nome: ").strip()
apelido = input("Apelido: ").strip()
palavra_passe = getpass.getpass("Palavra-passe: ")

if Utilizador.objects.filter(username=username).exists():
    sys.exit("Esse nome de utilizador já existe.")

Utilizador.objects.create_user(
    username=username, email=email, password=palavra_passe,
    first_name=nome, last_name=apelido, tipo=Utilizador.Tipo.COORDENADOR,
)
print("Coordenador criado.")