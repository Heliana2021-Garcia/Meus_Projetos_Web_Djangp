"""Cria (ou apaga) contas de teste para desenvolvimento e demonstracao.

Uso:
    python manage.py criar_perfis_teste            # cria as contas em falta
    python manage.py criar_perfis_teste --apagar   # apaga as contas de teste

Credenciais: tipo#@gmail.com / #030221h  (# = numero, a comecar em 2).
ATENCAO: senhas previsiveis. Usar apenas em ambiente de desenvolvimento.
"""
import re
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.contas.models import Utilizador
from apps.empresas.models import Empresa, Orientador
from apps.estudantes.models import Curso, PerfilEstudante

PRIMEIROS = [
    "Joao", "Maria", "Antonio", "Ana", "Manuel", "Teresa", "Pedro", "Luzia",
    "Domingos", "Isabel", "Francisco", "Josefa", "Paulo", "Catarina", "Adriano",
    "Beatriz", "Edson", "Helena", "Fernando", "Sandra", "Miguel", "Rosa",
    "Eduardo", "Celeste", "Bruno", "Judite", "Carlos", "Filomena", "Nelson", "Zulmira",
]
APELIDOS = [
    "Silva", "Santos", "Pereira", "Fernandes", "Gomes", "Domingos", "Quintas",
    "Cardoso", "Baptista", "Manuel", "Cabral", "Tavares", "Neto", "Lopes",
    "Kiala", "Mateus", "Sebastiao", "Francisco", "Afonso", "Machado",
    "Mendes", "Rocha", "Vieira", "Costa", "Ferreira", "Miguel", "Pinto", "Samuel",
]
SECTORES = [
    "Telecomunicacoes", "Banca", "Petroleo e Gas", "Tecnologias de Informacao",
    "Seguros", "Comercio", "Energia", "Servicos Publicos", "Consultoria", "Educacao",
]
CARGOS = [
    "Engenheiro de Software", "Analista de Sistemas", "Gestor de Projectos",
    "Administrador de Redes", "Analista de Dados", "Responsavel de TI",
]
PADRAO = re.compile(r"^(estudante|empresa|orientador|coordenador)\d+@gmail\.com$")

N_EMPRESAS = 30       # empresa2 .. empresa31
N_ORIENTADORES = 60   # orientador2 .. orientador61
N_ESTUDANTES = 120    # estudante2 .. estudante121
N_COORDENADORES = 10  # coordenador2 .. coordenador11


def nome(n):
    p = PRIMEIROS[n % len(PRIMEIROS)]
    a = APELIDOS[(n // len(PRIMEIROS) + n) % len(APELIDOS)]
    return p, a


class Command(BaseCommand):
    help = "Cria ou apaga contas de teste (estudantes, empresas, orientadores, coordenadores)."

    def add_arguments(self, parser):
        parser.add_argument("--apagar", action="store_true", help="Apaga as contas de teste.")

    def conta(self, tipo_slug, n, tipo, first, last):
        email = f"{tipo_slug}{n}@gmail.com"
        u = Utilizador.objects.filter(email=email).first()
        if u:
            return u, False
        u = Utilizador.objects.create_user(
            username=email, email=email, password=f"{n}030221h",
            first_name=first, last_name=last, tipo=tipo,
        )
        return u, True

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["apagar"]:
            return self.apagar()

        cursos = list(Curso.objects.order_by("sigla"))
        if not cursos:
            self.stderr.write("Nao existem cursos. Crie-os antes.")
            return
        novos = {"empresa": 0, "orientador": 0, "estudante": 0, "coordenador": 0}

        # Empresas
        empresas = []
        for i in range(N_EMPRESAS):
            n = i + 2
            p, a = nome(n)
            u, criado = self.conta("empresa", n, Utilizador.Tipo.EMPRESA, p, a)
            emp = Empresa.objects.filter(utilizador=u).first()
            if emp is None:
                emp = Empresa.objects.create(
                    utilizador=u,
                    nome=f"{a} {SECTORES[n % len(SECTORES)]} Lda {n}",
                    nif=f"5417{n:06d}",
                    tipo=Empresa.Tipo.PARCEIRA if n % 3 == 0 else Empresa.Tipo.GERAL,
                    sector=SECTORES[n % len(SECTORES)],
                    telefone=f"92{n:07d}"[:9],
                    endereco="Luanda",
                )
                emp.validar_nif()
            if criado:
                novos["empresa"] += 1
            empresas.append(emp)

        # Orientadores (distribuidos pelas empresas)
        for i in range(N_ORIENTADORES):
            n = i + 2
            p, a = nome(n + 7)
            u, criado = self.conta("orientador", n, Utilizador.Tipo.ORIENTADOR, p, a)
            if not Orientador.objects.filter(utilizador=u).exists():
                Orientador.objects.create(
                    utilizador=u, empresa=empresas[i % len(empresas)],
                    cargo=CARGOS[n % len(CARGOS)],
                )
            if criado:
                novos["orientador"] += 1

        # Estudantes (anos e medias variados; alguns inelegiveis de proposito)
        anos = [3, 4, 5, 3, 4, 2, 3, 4, 1, 5]
        for i in range(N_ESTUDANTES):
            n = i + 2
            p, a = nome(n + 3)
            u, criado = self.conta("estudante", n, Utilizador.Tipo.ESTUDANTE, p, a)
            if not PerfilEstudante.objects.filter(utilizador=u).exists():
                media = Decimal("10.00") + Decimal((n * 37) % 90) / Decimal(10)
                PerfilEstudante.objects.create(
                    utilizador=u,
                    numero_estudante=f"20{n:05d}",
                    curso=cursos[n % len(cursos)],
                    ano_frequencia=anos[n % 10],
                    media_geral=media.quantize(Decimal("0.01")),
                )
            if criado:
                novos["estudante"] += 1

        # Coordenadores
        for i in range(N_COORDENADORES):
            n = i + 2
            p, a = nome(n + 11)
            _, criado = self.conta("coordenador", n, Utilizador.Tipo.COORDENADOR, p, a)
            if criado:
                novos["coordenador"] += 1

        self.stdout.write(self.style.SUCCESS(
            "Criadas: {estudante} estudantes, {empresa} empresas, "
            "{orientador} orientadores, {coordenador} coordenadores.".format(**novos)
        ))
        self.stdout.write("Exemplo: estudante2@gmail.com / 2030221h")

    def apagar(self):
        apagadas = 0
        for u in Utilizador.objects.filter(is_superuser=False):
            if PADRAO.match(u.email):
                u.delete()
                apagadas += 1
        self.stdout.write(self.style.WARNING(f"Contas de teste apagadas: {apagadas}"))