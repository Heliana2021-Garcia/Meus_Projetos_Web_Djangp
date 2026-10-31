"""Cenário mínimo para demonstrar o SIGEST (apenas desenvolvimento).

Uso:  python manage.py shell -c "exec(open('scripts/criar_demo.py', encoding='utf-8').read())"
É seguro repetir: não duplica o que já existe.
"""


def criar():
    from decimal import Decimal

    from django.contrib.auth import get_user_model

    from apps.candidaturas.models import Candidatura
    from apps.relatorios.filtros_estagios import modelo_curso
    from apps.vagas.models import Vaga

    Utilizador = get_user_model()
    PerfilEstudante = Candidatura._meta.get_field("estudante").related_model
    Empresa = Vaga._meta.get_field("empresa").related_model
    Curso = modelo_curso()
    senha = "Demo#2026"

    def utilizador(username, tipo, nome, apelido):
        u, criado = Utilizador.objects.get_or_create(
            username=username,
            defaults={"tipo": tipo, "first_name": nome, "last_name": apelido, "email": f"{username}@demo.ao"},
        )
        if criado:
            u.set_password(senha)
            u.save()
        return u

    curso, _ = Curso.objects.get_or_create(sigla="EI", defaults={"nome": "Engenharia Informática"})

    utilizador("demo_coord", "COORDENADOR", "Carlos", "Coordenador")

    aluno = utilizador("demo_estudante", "ESTUDANTE", "Ana", "Estudante")
    PerfilEstudante.objects.get_or_create(
        utilizador=aluno,
        defaults={
            "numero_estudante": "DEMO001", "curso": curso,
            "ano_frequencia": 3, "media_geral": Decimal("15"),
        },
    )

    dono = utilizador("demo_empresa", "EMPRESA", "Eva", "Empresa")
    empresa, criada = Empresa.objects.get_or_create(
        utilizador=dono, defaults={"nome": "Empresa Demo, Lda", "nif": "5000000001"}
    )
    if criada:
        empresa.validar_nif()

    if not Vaga.objects.filter(empresa=empresa, titulo="Estagiário de Redes").exists():
        vaga = Vaga.objects.create(
            empresa=empresa, titulo="Estagiário de Redes", numero_vagas=2,
            duracao_meses=3, area="Redes e Sistemas",
        )
        vaga.publicar()

    print("OK cenário de demonstração criado.")
    print(f"Palavra-passe de todas as contas: {senha}")
    print("Entrar com o EMAIL: demo_coord@demo.ao (coordenador), demo_estudante@demo.ao, demo_empresa@demo.ao")
    print("O orientador cria-se no ecrã, pela empresa, em 'Orientadores'.")


criar()