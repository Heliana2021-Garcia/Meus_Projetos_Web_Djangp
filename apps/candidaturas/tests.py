from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.models import Notificacao
from apps.empresas.models import Empresa
from apps.estudantes.models import Curso, PerfilEstudante
from apps.relatorios import servicos
from apps.vagas.models import Vaga

from .models import Candidatura

User = get_user_model()


class FluxoCandidaturaTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nome="Engenharia Informatica", sigla="EI")

        self.u_aluno = User.objects.create_user(
            "aluno", "aluno@teste.ao", "x", tipo="ESTUDANTE"
        )
        self.aluno = PerfilEstudante.objects.create(
            utilizador=self.u_aluno, numero_estudante="A1", curso=self.curso,
            ano_frequencia=3, media_geral=Decimal("15.00"),
        )

        self.u_emp1 = User.objects.create_user("emp1", "emp1@teste.ao", "x", tipo="EMPRESA")
        self.u_emp2 = User.objects.create_user("emp2", "emp2@teste.ao", "x", tipo="EMPRESA")
        self.emp1 = Empresa.objects.create(utilizador=self.u_emp1, nome="Emp 1", nif="1000000001")
        self.emp2 = Empresa.objects.create(utilizador=self.u_emp2, nome="Emp 2", nif="1000000002")
        for emp in (self.emp1, self.emp2):
            emp.validar_nif()

        self.vaga1 = Vaga.objects.create(empresa=self.emp1, titulo="Vaga 1")
        self.vaga2 = Vaga.objects.create(empresa=self.emp2, titulo="Vaga 2")
        self.vaga1.publicar()
        self.vaga2.publicar()

    def _aprovar(self, candidatura):
        candidatura.mover_para("ENTREVISTA")
        candidatura.mover_para("PROPOSTA")
        candidatura.mover_para("APROVADO")

    def test_aprovacao_cancela_as_outras_candidaturas_ativas(self):
        c1 = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga1)
        c2 = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga2)

        self._aprovar(c1)

        c1.refresh_from_db()
        c2.refresh_from_db()
        self.aluno.refresh_from_db()
        self.assertEqual(c1.estado, Candidatura.Estado.APROVADO)
        self.assertEqual(c2.estado, Candidatura.Estado.CANCELADA)
        self.assertEqual(self.aluno.estado, PerfilEstudante.Estado.OCUPADO)

    def test_candidatura_cancelada_nao_pode_ser_movida(self):
        c1 = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga1)
        c2 = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga2)
        self._aprovar(c1)
        c2.refresh_from_db()
        with self.assertRaises(ValidationError):
            c2.mover_para("ENTREVISTA")

    def test_rejeitar_exige_feedback(self):
        c1 = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga1)
        with self.assertRaises(ValidationError):
            c1.mover_para("REJEITADO", "   ")
        c1.mover_para("REJEITADO", "Perfil não adequado.")
        self.assertEqual(c1.estado, Candidatura.Estado.REJEITADO)

    def test_notificacoes_para_empresa_e_estudante(self):
        c1 = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga1)
        self.assertEqual(Notificacao.objects.filter(destinatario=self.u_emp1).count(), 1)

        c1.mover_para("ENTREVISTA")
        self.assertEqual(Notificacao.objects.filter(destinatario=self.u_aluno).count(), 1)

    def test_empresa_e_avisada_do_cancelamento_automatico(self):
        c1 = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga1)
        Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga2)
        self._aprovar(c1)
        # nova candidatura + cancelamento
        self.assertEqual(Notificacao.objects.filter(destinatario=self.u_emp2).count(), 2)

    def test_email_e_enviado(self):
        Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["emp1@teste.ao"])

    def test_indicadores_de_empregabilidade(self):
        c1 = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga1)
        self._aprovar(c1)
        c1.concluir_estagio(Decimal("16"))

        ind = servicos.indicadores_gerais()
        self.assertEqual(ind["colocados"], 1)
        self.assertEqual(ind["taxa_colocacao"], 100)
        self.assertEqual(ind["estagios_concluidos"], 1)
        self.assertEqual(ind["media_avaliacoes"], Decimal("16"))

        por_curso = servicos.resumo_por_curso()
        self.assertEqual(por_curso[0]["colocados"], 1)