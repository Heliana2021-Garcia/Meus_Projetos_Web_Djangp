from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.candidaturas.models import Candidatura
from apps.documentos.models import CartaEncaminhamento
from apps.empresas.models import Empresa
from apps.estudantes.models import Curso, PerfilEstudante
from apps.vagas.models import Vaga

User = get_user_model()


class ControloDeAcessoTests(TestCase):
    def setUp(self):
        curso = Curso.objects.create(nome="Engenharia Informatica", sigla="EI")

        self.admin = User.objects.create_user("adm", "adm@t.ao", "x", tipo="ADMIN")

        self.u_aluno = User.objects.create_user("aluno", "aluno@t.ao", "x", tipo="ESTUDANTE")
        self.aluno = PerfilEstudante.objects.create(
            utilizador=self.u_aluno, numero_estudante="A1", curso=curso,
            ano_frequencia=3, media_geral=Decimal("15"),
        )
        self.u_aluno2 = User.objects.create_user("aluno2", "aluno2@t.ao", "x", tipo="ESTUDANTE")
        PerfilEstudante.objects.create(
            utilizador=self.u_aluno2, numero_estudante="A2", curso=curso,
            ano_frequencia=3, media_geral=Decimal("15"),
        )

        self.u_emp = User.objects.create_user("emp", "emp@t.ao", "x", tipo="EMPRESA")
        self.empresa = Empresa.objects.create(utilizador=self.u_emp, nome="Emp", nif="1000000001")
        self.empresa.validar_nif()
        self.u_emp2 = User.objects.create_user("emp2", "emp2@t.ao", "x", tipo="EMPRESA")
        Empresa.objects.create(utilizador=self.u_emp2, nome="Emp 2", nif="1000000002")

        self.vaga = Vaga.objects.create(empresa=self.empresa, titulo="Vaga")
        self.vaga.publicar()

    def test_anonimo_vai_para_o_login(self):
        resposta = self.client.get(reverse("estudantes:painel"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("contas:entrar"), resposta.url)

    def test_inicio_redireciona_para_o_painel_de_cada_tipo(self):
        esperado = {
            self.admin: "relatorios:painel",
            self.u_aluno: "estudantes:painel",
            self.u_emp: "empresas:painel",
        }
        for utilizador, painel in esperado.items():
            self.client.force_login(utilizador)
            resposta = self.client.get(reverse("contas:inicio"))
            self.assertRedirects(resposta, reverse(painel), fetch_redirect_response=False)

    def test_estudante_nao_acede_a_areas_da_empresa_nem_da_administracao(self):
        self.client.force_login(self.u_aluno)
        for nome in ("vagas:minhas", "relatorios:painel", "relatorios:dashboard"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 403, nome)

    def test_empresa_nao_acede_ao_feed_nem_a_administracao(self):
        self.client.force_login(self.u_emp)
        for nome in ("vagas:feed", "relatorios:dashboard", "relatorios:exportar"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 403, nome)

    def test_administrador_acede_ao_dashboard_e_a_exportacao(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("relatorios:dashboard")).status_code, 200)
        exportacao = self.client.get(reverse("relatorios:exportar"))
        self.assertEqual(exportacao.status_code, 200)
        self.assertIn("text/csv", exportacao["Content-Type"])

    def test_estudante_nao_pode_mover_candidaturas(self):
        candidatura = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga)
        self.client.force_login(self.u_aluno)
        resposta = self.client.post(
            reverse("candidaturas:mover", args=[candidatura.pk]), {"novo_estado": "ENTREVISTA"}
        )
        self.assertEqual(resposta.status_code, 403)

    def test_carta_so_pode_ser_aberta_pelos_envolvidos(self):
        candidatura = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga)
        for estado in ("ENTREVISTA", "PROPOSTA", "APROVADO"):
            candidatura.mover_para(estado)
        carta, _ = CartaEncaminhamento.emitir(candidatura, self.admin)
        url = reverse("documentos:descarregar", args=[carta.pk])

        for utilizador in (self.u_aluno2, self.u_emp2):
            self.client.force_login(utilizador)
            self.assertEqual(self.client.get(url).status_code, 403)

        for utilizador in (self.u_aluno, self.u_emp, self.admin):
            self.client.force_login(utilizador)
            resposta = self.client.get(url)
            self.assertEqual(resposta.status_code, 200)
            self.assertEqual(resposta["Content-Type"], "application/pdf")