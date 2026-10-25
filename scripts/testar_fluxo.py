import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django
django.setup()

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.candidaturas.models import Candidatura
from apps.core.models import Tecnologia
from apps.empresas.models import Empresa
from apps.estudantes.models import Curso, PerfilEstudante
from apps.vagas.models import Vaga

User = get_user_model()


def tentar(descricao, funcao):
    try:
        funcao()
        print("OK   |", descricao)
    except ValidationError as erro:
        print("ERRO |", descricao, "->", "; ".join(erro.messages))


with transaction.atomic():
    curso, _ = Curso.objects.get_or_create(sigla="EI", defaults={"nome": "Engenharia Informatica"})

    u1 = User.objects.create_user("t_aluno", "t_aluno@teste.ao", "x", tipo="ESTUDANTE")
    u2 = User.objects.create_user("t_novato", "t_novato@teste.ao", "x", tipo="ESTUDANTE")
    u3 = User.objects.create_user("t_empresa", "t_empresa@teste.ao", "x", tipo="EMPRESA")

    aluno = PerfilEstudante.objects.create(
        utilizador=u1, numero_estudante="T001", curso=curso,
        ano_frequencia=3, media_geral=Decimal("15.00"),
    )
    novato = PerfilEstudante.objects.create(
        utilizador=u2, numero_estudante="T002", curso=curso,
        ano_frequencia=2, media_geral=Decimal("13.50"),
    )
    empresa = Empresa.objects.create(
        utilizador=u3, nome="Empresa Teste", nif="900000001", tipo="PARCEIRA"
    )
    vaga = Vaga.objects.create(empresa=empresa, titulo="Estagio Django")

    py = Tecnologia.objects.create(nome="ZZ-Python")
    dj = Tecnologia.objects.create(nome="ZZ-Django")
    vaga.tecnologias.add(py, dj)
    aluno.tecnologias.add(py)
    print("Compatibilidade (esperado 50):", vaga.compatibilidade(aluno))

    tentar("publicar com NIF por validar (deve falhar)", vaga.publicar)
    empresa.validar_nif()
    tentar("publicar com NIF validado", vaga.publicar)

    tentar(
        "candidatura do 2o ano com media 13.5 (deve falhar)",
        lambda: Candidatura.objects.create(estudante=novato, vaga=vaga),
    )
    cand = Candidatura.objects.create(estudante=aluno, vaga=vaga)
    print("Candidatura criada com estado:", cand.estado)
    tentar(
        "candidatura duplicada (deve falhar)",
        lambda: Candidatura.objects.create(estudante=aluno, vaga=vaga),
    )

    tentar("saltar de Pendente para Proposta (deve falhar)", lambda: cand.mover_para("PROPOSTA"))
    tentar("Pendente -> Entrevista", lambda: cand.mover_para("ENTREVISTA"))
    tentar("rejeitar sem feedback (deve falhar)", lambda: cand.mover_para("REJEITADO"))
    tentar("Entrevista -> Proposta", lambda: cand.mover_para("PROPOSTA"))
    tentar("Proposta -> Aprovado", lambda: cand.mover_para("APROVADO"))

    aluno.refresh_from_db()
    print("Estado do aluno apos aprovacao (esperado OCUPADO):", aluno.estado)

    tentar("avaliacao 25 (deve falhar)", lambda: cand.concluir_estagio(25))
    tentar("concluir estagio com nota 17", lambda: cand.concluir_estagio(17))

    aluno.refresh_from_db()
    print("Estado do aluno apos conclusao (esperado DISPONIVEL):", aluno.estado)

    transaction.set_rollback(True)

print("Dados de teste revertidos.")
