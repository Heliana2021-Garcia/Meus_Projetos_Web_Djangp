"""Cria estagiarios de teste: 20 em curso, 15 concluidos e 5 concluidos e efectivados.

Uso:  python manage.py criar_estagios_teste
Requer os dados de criar_perfis_teste (estudantes, empresas, orientadores e vagas).
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from apps.candidaturas import servicos_avaliacao
from apps.candidaturas.models import AvaliacaoMensal, Candidatura, RegistoDiario, RelatorioEstagio
from apps.empresas.models import Orientador
from apps.estudantes.models import PerfilEstudante
from apps.vagas.models import Vaga

N_EM_CURSO = 20
N_CONCLUIDOS = 15
N_EFECTIVADOS = 5

ACTIVIDADES = [
    "Configura\u00e7\u00e3o do ambiente de trabalho e leitura da documenta\u00e7\u00e3o interna.",
    "Apoio na an\u00e1lise de requisitos com a equipa.",
    "Desenvolvimento de funcionalidades do sistema interno.",
    "Testes e correc\u00e7\u00e3o de erros reportados pelos utilizadores.",
    "Elabora\u00e7\u00e3o de documenta\u00e7\u00e3o t\u00e9cnica.",
    "Participa\u00e7\u00e3o na reuni\u00e3o semanal e apresenta\u00e7\u00e3o do progresso.",
    "Apoio no suporte a utilizadores e resolu\u00e7\u00e3o de incidentes.",
    "Revis\u00e3o de c\u00f3digo e boas pr\u00e1ticas com o orientador.",
]
COMENTARIOS = [
    "Boa disponibilidade e acompanhamento.",
    "Orienta\u00e7\u00e3o clara; gostava de mais momentos de feedback.",
    "Explica bem as tarefas e est\u00e1 sempre dispon\u00edvel.",
    "Bom ambiente de trabalho e tarefas adequadas ao curso.",
]


class Command(BaseCommand):
    help = "Cria 20 estagios em curso, 15 concluidos e 5 concluidos e efectivados."

    def add_arguments(self, parser):
        parser.add_argument("--forcar", action="store_true", help="Cria mesmo que ja existam candidaturas.")
        parser.add_argument("--em-curso", type=int, default=N_EM_CURSO)
        parser.add_argument("--concluidos", type=int, default=N_CONCLUIDOS)
        parser.add_argument("--efectivados", type=int, default=N_EFECTIVADOS)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.dummy.EmailBackend")
    def handle(self, *args, **opts):
        if Candidatura.objects.exists() and not opts["forcar"]:
            self.stderr.write("Ja existem candidaturas. Use --forcar para criar mais.")
            return
        rng = random.Random(2026)
        hoje = timezone.localdate()

        elegiveis = [
            p for p in PerfilEstudante.objects.select_related("utilizador").order_by("pk")
            if p.ano_frequencia >= PerfilEstudante.ANO_MINIMO_CANDIDATURA
            and p.media_geral >= PerfilEstudante.MEDIA_MINIMA_CANDIDATURA
            and not Candidatura.objects.filter(estudante=p).exists()
        ]
        plano = ["CURSO"] * opts["em_curso"] + ["CONCLUIDO"] * opts["concluidos"] + ["EFECTIVADO"] * opts["efectivados"]
        if len(elegiveis) < len(plano):
            self.stderr.write(f"So ha {len(elegiveis)} estudantes elegiveis; sao precisos {len(plano)}.")
            return
        vagas = list(
            Vaga.objects.filter(estado="ABERTA", empresa__nif_validado=True)
            .select_related("empresa__utilizador").order_by("pk")
        )
        rng.shuffle(vagas)
        rng.shuffle(elegiveis)

        carga = {}
        criados = {"CURSO": [], "CONCLUIDO": [], "EFECTIVADO": []}
        falhas = []
        concluidos_n = 0
        for i, tipo in enumerate(plano):
            perfil = elegiveis[i]
            vaga = next((v for v in (vagas[(i + j) % len(vagas)] for j in range(len(vagas))) if v.publica and v.aceita_curso(perfil.curso) and Orientador.objects.filter(empresa=v.empresa).exists()), None)
            if vaga is None:
                falhas.append(perfil.utilizador.email + ': sem vaga compativel')
                continue
            orientadores = list(Orientador.objects.filter(empresa=vaga.empresa).select_related("utilizador"))
            if not orientadores:
                falhas.append(f"{vaga.empresa.nome}: sem orientadores")
                continue
            orientador = min(orientadores, key=lambda o: carga.get(o.pk, 0))
            try:
                with transaction.atomic():
                    c = self.criar_estagio(i, tipo, perfil, vaga, orientador, hoje, concluidos_n)
            except Exception as erro:  # noqa: BLE001
                falhas.append(f"{perfil.utilizador.email}: {erro}")
                continue
            if tipo == "CURSO":
                carga[orientador.pk] = carga.get(orientador.pk, 0) + 1
            else:
                concluidos_n += 1
            criados[tipo].append((perfil.utilizador.email, vaga.empresa.utilizador.email, orientador.utilizador.email))

        self.stdout.write(self.style.SUCCESS(
            f"Estagios criados: {len(criados['CURSO'])} em curso, {len(criados['CONCLUIDO'])} concluidos, "
            f"{len(criados['EFECTIVADO'])} concluidos e efectivados."
        ))
        for nome, lista in criados.items():
            if lista:
                est, emp, ori = lista[0]
                self.stdout.write(f"Exemplo {nome}: estudante {est} | empresa {emp} | orientador {ori}")
        for f in falhas:
            self.stdout.write(self.style.WARNING("FALHOU: " + f))

    def criar_estagio(self, i, tipo, perfil, vaga, orientador, hoje, concluidos_n):
        c = Candidatura.objects.create(estudante=perfil, vaga=vaga)
        try:
            with transaction.atomic():
                c.mover_para("PROPOSTA")
                c.mover_para("APROVADO")
        except Exception:  # noqa: BLE001
            Candidatura.objects.filter(pk=c.pk).update(estado="APROVADO")
            c.refresh_from_db()
        c.atribuir_orientador(orientador)
        c.confirmar_inicio(vaga.empresa.utilizador)
        c.confirmar_inicio(perfil.utilizador)
        c.refresh_from_db()

        dur = vaga.duracao_meses
        if tipo == "CURSO":
            decorridos = min(10 + (i * 13) % 90, 30 * dur - 5)
            inicio = hoje - timedelta(days=decorridos)
        else:
            fim_real = hoje - timedelta(days=5 + (i * 7) % 60)
            inicio = fim_real - timedelta(days=30 * dur)
            decorridos = 30 * dur
        fim = inicio + timedelta(days=30 * dur)
        Candidatura.objects.filter(pk=c.pk).update(data_inicio=inicio, data_fim=fim)
        c.refresh_from_db()

        dias = list(range(1, decorridos + 1, 3))
        for pos, d in enumerate(dias):
            pendente = tipo == "CURSO" and pos >= len(dias) - 2
            nota = None if pendente else Decimal(str(10 + ((i * 7 + d * 3) % 19) / 2))
            RegistoDiario.objects.create(
                candidatura=c, data=inicio + timedelta(days=d),
                descricao=ACTIVIDADES[(i + pos) % len(ACTIVIDADES)],
                estado="SUBMETIDO" if pendente else "VALIDADO",
                nota=nota,
                validado_por=None if pendente else orientador.utilizador,
            )

        meses = dur if tipo != "CURSO" else decorridos // 30
        if tipo == "CURSO" and i % 3 == 0 and meses > 0:
            meses -= 1  # avaliacao mensal em atraso
        for mes in range(1, meses + 1):
            AvaliacaoMensal.objects.create(
                candidatura=c, mes=mes, orientador=orientador,
                nota=Decimal(str(12 + ((i + mes * 5) % 15) / 2)),
                comentario=COMENTARIOS[(i + mes) % len(COMENTARIOS)],
            )

        if tipo != "CURSO":
            RelatorioEstagio.objects.create(
                candidatura=c, tipo="FINAL", titulo="Relat\u00f3rio final de est\u00e1gio",
                conteudo="Resumo das actividades desenvolvidas, compet\u00eancias adquiridas e conclus\u00f5es do est\u00e1gio.",
                estado="VALIDADO",
            )
            servicos_avaliacao.concluir(c, vaga.empresa.utilizador)
            c.refresh_from_db()
            fecho = timezone.make_aware(datetime.combine(fim + timedelta(days=1), time(10, 0)))
            c.concluida_em = fecho
            if tipo == "EFECTIVADO":
                c.efectivado, c.efectivado_em = True, fecho + timedelta(days=3)
            elif concluidos_n % 2 == 0:
                c.efectivado, c.efectivado_em = False, fecho + timedelta(days=3)
            c.save(update_fields=["concluida_em", "efectivado", "efectivado_em", "atualizado_em"])
        return c