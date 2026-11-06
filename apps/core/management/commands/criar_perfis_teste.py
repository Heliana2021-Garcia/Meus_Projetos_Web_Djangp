"""Cria (ou apaga) contas de teste para desenvolvimento e demonstracao.

Uso:
    python manage.py criar_perfis_teste              # cria o que falta
    python manage.py criar_perfis_teste --reiniciar  # apaga tudo (menos admin e
                                                     # coordenadores reais) e recria
    python manage.py criar_perfis_teste --apagar     # apaga so as contas de teste

Credenciais: tipo#@gmail.com / #030221h  (# = numero, a comecar em 2; a senha
e igual para todas as contas).
ATENCAO: senha previsivel. Usar apenas em ambiente de desenvolvimento.
"""
import re
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.contas.models import Utilizador
from apps.core.models import Tecnologia
from apps.empresas.models import Empresa, Orientador
from apps.estudantes.models import Curso, PerfilEstudante
from apps.vagas.models import Vaga

SENHA = "#030221h"

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
AREAS = [
    "Desenvolvimento de Software", "Redes e Telecomunica\u00e7\u00f5es", "An\u00e1lise de Dados",
    "Seguran\u00e7a Inform\u00e1tica", "Suporte T\u00e9cnico", "Administra\u00e7\u00e3o de Sistemas",
    "Bases de Dados", "Gest\u00e3o de Projectos de TI",
]
LOCAIS = ["Luanda", "Viana", "Talatona", "Belas", "Cacuaco", "Benguela", "Huambo", "Lubango"]
MODALIDADES = ["PRESENCIAL", "HIBRIDO", "REMOTO", "PRESENCIAL"]
DURACOES = [3, 6, 4, 3, 2]
ESTADOS = ["ABERTA"] * 7 + ["EM_ANALISE", "RASCUNHO", "ENCERRADA"]
FASES = [(True, False, True), (False, True, True), (True, True, True), (False, False, False), (True, False, False)]

PADRAO = re.compile(r"^(estudante|empresa|orientador|coordenador)\d+@gmail\.com$")

N_EMPRESAS = 40       # empresa2 .. empresa41
N_ORIENTADORES = 80   # orientador2 .. orientador81
N_ESTUDANTES = 170    # estudante2 .. estudante171
N_COORDENADORES = 10  # coordenador2 .. coordenador11   (total: 300)


def nome(n):
    p = PRIMEIROS[n % len(PRIMEIROS)]
    a = APELIDOS[(n // len(PRIMEIROS) + n) % len(APELIDOS)]
    return p, a


class Command(BaseCommand):
    help = "Cria ou apaga contas de teste (estudantes, empresas, orientadores, coordenadores) e vagas."

    def add_arguments(self, parser):
        parser.add_argument("--apagar", action="store_true", help="Apaga as contas de teste.")
        parser.add_argument(
            "--reiniciar", action="store_true",
            help="Apaga todos os utilizadores (menos admin e coordenadores reais) e recria os dados de teste.",
        )

    def conta(self, tipo_slug, n, tipo, first, last):
        email = f"{tipo_slug}{n}@gmail.com"
        u = Utilizador.objects.filter(email=email).first()
        if u:
            return u, False
        u = Utilizador.objects.create_user(
            username=email, email=email, password=SENHA,
            first_name=first, last_name=last, tipo=tipo,
        )
        return u, True

    def criar_vagas(self, emp, n, cursos, tecnologias):
        if emp.vagas.exists():
            return 0
        hoje = timezone.localdate()
        total = 3 + (n % 5)
        for k in range(total):
            area = AREAS[(n + k) % len(AREAS)]
            estado = ESTADOS[(n + k) % len(ESTADOS)]
            if estado == "ABERTA":
                dias = -3 if (n + k) % 9 == 0 else 10 + (n * (k + 3)) % 80
            elif estado == "ENCERRADA":
                dias = -10
            else:
                dias = 30
            teste, curriculo, entrevista = FASES[(n + k) % len(FASES)]
            vaga = Vaga.objects.create(
                empresa=emp,
                titulo=f"Estagi\u00e1rio de {area}",
                descricao=(
                    f"A {emp.nome} procura estudante para est\u00e1gio na \u00e1rea de {area}, "
                    "com acompanhamento de um orientador da empresa."
                ),
                requisitos=(
                    "Frequ\u00eancia do 3.\u00ba ano ou superior; boa capacidade de comunica\u00e7\u00e3o; "
                    "vontade de aprender."
                ),
                numero_vagas=1 + (n + k) % 4,
                localizacao=LOCAIS[(n + k) % len(LOCAIS)],
                modalidade=MODALIDADES[(n + k) % len(MODALIDADES)],
                duracao_meses=DURACOES[(n + k) % len(DURACOES)],
                data_limite=hoje + timezone.timedelta(days=dias),
                estado=estado,
                area=area,
                tipo_estagio="CURRICULAR" if (n + k) % 3 else "PROFISSIONAL",
                documentos_exigidos="Curr\u00edculo\nDeclara\u00e7\u00e3o de notas\nDeclara\u00e7\u00e3o de frequ\u00eancia",
                fase_teste=teste,
                fase_curriculo=curriculo,
                fase_entrevista=entrevista,
            )
            if (n + k) % 4 != 0:
                vaga.cursos.set([cursos[(n + k) % len(cursos)], cursos[(n + k + 1) % len(cursos)]])
            if tecnologias:
                vaga.tecnologias.set([tecnologias[(n + k + j) % len(tecnologias)] for j in range(3)])
        return total

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["apagar"]:
            return self.apagar()
        if opts["reiniciar"]:
            if not self.limpar():
                return

        cursos = list(Curso.objects.order_by("sigla"))
        if not cursos:
            self.stderr.write("Nao existem cursos. Crie-os antes.")
            return
        tecnologias = list(Tecnologia.objects.order_by("pk"))
        novos = {"empresa": 0, "orientador": 0, "estudante": 0, "coordenador": 0, "vagas": 0}

        # Empresas (cada uma com varias vagas)
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
            novos["vagas"] += self.criar_vagas(emp, n, cursos, tecnologias)
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
            "Criadas: {estudante} estudantes, {empresa} empresas, {orientador} orientadores, "
            "{coordenador} coordenadores e {vagas} vagas.".format(**novos)
        ))
        self.stdout.write("Exemplo: estudante2@gmail.com / " + SENHA)

    def _apagar(self, objecto):
        from django.db.models.deletion import ProtectedError

        for _ in range(50):
            try:
                objecto.delete()
                return
            except ProtectedError as e:
                for o in list(e.protected_objects):
                    self._apagar(o)
        objecto.delete()

    def limpar(self):
        """Apaga tudo menos superutilizadores, ADMIN e coordenadores reais (fora do padrao de teste)."""
        alvo = [
            u for u in Utilizador.objects.all()
            if not u.is_superuser
            and u.tipo != "ADMIN"
            and not (u.tipo == Utilizador.Tipo.COORDENADOR and not PADRAO.match(u.email))
        ]
        contagem = {}
        for u in alvo:
            contagem[u.tipo] = contagem.get(u.tipo, 0) + 1
        self.stdout.write(self.style.WARNING(
            f"Vai apagar {len(alvo)} utilizadores {contagem}, com as vagas, candidaturas, "
            "estagios, documentos, notificacoes e registos associados."
        ))
        if input("Escreva APAGAR para confirmar: ").strip() != "APAGAR":
            self.stdout.write("Cancelado. Nada foi alterado.")
            return False
        from apps.candidaturas.models import Candidatura
        self._apagar(Candidatura.objects.all())
        for u in alvo:
            self._apagar(u)
        self.stdout.write(self.style.WARNING(f"Utilizadores apagados: {len(alvo)}"))
        return True

    def apagar(self):
        apagadas = 0
        for u in Utilizador.objects.filter(is_superuser=False):
            if PADRAO.match(u.email):
                u.delete()
                apagadas += 1
        self.stdout.write(self.style.WARNING(f"Contas de teste apagadas: {apagadas}"))