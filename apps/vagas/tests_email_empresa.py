from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.candidaturas.models import Candidatura
from apps.empresas.models import Empresa
from apps.estudantes.models import Curso, PerfilEstudante
from apps.vagas.models import Vaga

User = get_user_model()
EMAIL = "rh@alfa.ao"


class EmailDaEmpresaTests(TestCase):
    def setUp(self):
        curso = Curso.objects.create(nome="Eng", sigla="E")
        self.u_aluno = User.objects.create_user("al@t.ao", "al@t.ao", "x", tipo="ESTUDANTE")
        self.aluno = PerfilEstudante.objects.create(
            utilizador=self.u_aluno, numero_estudante="A1", curso=curso,
            ano_frequencia=3, media_geral=Decimal("15"),
        )
        u_emp = User.objects.create_user(EMAIL, EMAIL, "x", tipo="EMPRESA")
        self.empresa = Empresa.objects.create(utilizador=u_emp, nome="Alfa", nif="1000000001")
        self.empresa.validar_nif()
        self.vaga = Vaga.objects.create(empresa=self.empresa, titulo="Vaga")
        self.vaga.publicar()
        self.coord = User.objects.create_user("co@t.ao", "co@t.ao", "x", tipo="COORDENADOR")

    def test_propriedade(self):
        self.assertEqual(self.empresa.email, EMAIL)

    def test_estudante_ve_o_email_no_feed_e_no_detalhe(self):
        self.client.force_login(self.u_aluno)
        self.assertContains(self.client.get(reverse("vagas:feed")), EMAIL)
        self.assertContains(self.client.get(reverse("vagas:detalhe", args=[self.vaga.pk])), EMAIL)

    def test_estudante_ve_o_email_nas_candidaturas_e_no_estagio(self):
        c = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga)
        self.client.force_login(self.u_aluno)
        self.assertContains(self.client.get(reverse("candidaturas:minhas")), EMAIL)
        for e in ("TESTE", "ENTREVISTA", "PROPOSTA", "APROVADO"):
            c.mover_para(e)
        self.assertContains(self.client.get(reverse("candidaturas:estagio")), EMAIL)

    def test_coordenador_ve_o_email_nas_vagas_em_analise_no_painel_e_nos_estagios(self):
        em_analise = Vaga.objects.create(empresa=self.empresa, titulo="Outra")
        em_analise.estado = Vaga.Estado.EM_ANALISE
        em_analise.save()
        self.client.force_login(self.coord)
        self.assertContains(self.client.get(reverse("relatorios:vagas_analise")), EMAIL)
        c = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga)
        for e in ("TESTE", "ENTREVISTA", "PROPOSTA", "APROVADO"):
            c.mover_para(e)
        self.assertContains(self.client.get(reverse("relatorios:painel")), EMAIL)
        self.assertContains(self.client.get(reverse("relatorios:estagios")), EMAIL)

    def test_coordenador_ve_o_email_da_empresa_com_nif_por_validar(self):
        u = User.objects.create_user("nova@x.ao", "nova@x.ao", "x", tipo="EMPRESA")
        Empresa.objects.create(utilizador=u, nome="Nova", nif="1000000002")
        self.client.force_login(self.coord)
        self.assertContains(self.client.get(reverse("relatorios:painel")), "nova@x.ao")
