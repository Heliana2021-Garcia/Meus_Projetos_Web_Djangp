from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.empresas.models import Empresa
from apps.estudantes.models import Curso, PerfilEstudante
from apps.vagas.models import Vaga

User = get_user_model()


class FiltrosFeedTests(TestCase):
    def setUp(self):
        curso = Curso.objects.create(nome="Engenharia Informatica", sigla="EI")
        u = User.objects.create_user("al@t.ao", "al@t.ao", "x", tipo="ESTUDANTE")
        PerfilEstudante.objects.create(
            utilizador=u, numero_estudante="A1", curso=curso, ano_frequencia=3, media_geral=Decimal("15"),
        )
        ue = User.objects.create_user("emp@t.ao", "emp@t.ao", "x", tipo="EMPRESA")
        empresa = Empresa.objects.create(utilizador=ue, nome="Emp", nif="1000000001")
        empresa.validar_nif()
        self.a = Vaga.objects.create(
            empresa=empresa, titulo="Vaga Luanda curta", localizacao="Luanda",
            duracao_meses=3, modalidade=Vaga.Modalidade.PRESENCIAL,
        )
        self.b = Vaga.objects.create(
            empresa=empresa, titulo="Vaga Benguela longa", localizacao="Benguela",
            duracao_meses=12, modalidade=Vaga.Modalidade.REMOTO,
        )
        for v in (self.a, self.b):
            v.publicar()
        self.client.force_login(u)

    def titulos(self, **filtros):
        resposta = self.client.get(reverse("vagas:feed"), filtros)
        self.assertEqual(resposta.status_code, 200)
        return {i["vaga"].titulo for i in resposta.context["itens"]}

    def test_sem_filtros_mostra_todas(self):
        self.assertEqual(len(self.titulos()), 2)

    def test_filtra_por_localizacao(self):
        self.assertEqual(self.titulos(localizacao="luanda"), {self.a.titulo})

    def test_filtra_por_duracao_maxima(self):
        self.assertEqual(self.titulos(duracao="6"), {self.a.titulo})
        self.assertEqual(len(self.titulos(duracao="12")), 2)

    def test_filtra_por_modalidade(self):
        self.assertEqual(self.titulos(modalidade=Vaga.Modalidade.REMOTO), {self.b.titulo})

    def test_valores_invalidos_sao_ignorados(self):
        self.assertEqual(len(self.titulos(duracao="abc", modalidade="xx")), 2)

    def test_filtros_combinados(self):
        self.assertEqual(self.titulos(localizacao="Luanda", duracao="12", modalidade="REMOTO"), set())


class PainelDocumentosTests(TestCase):
    def setUp(self):
        curso = Curso.objects.create(nome="Eng", sigla="E")
        self.u = User.objects.create_user("al@t.ao", "al@t.ao", "x", tipo="ESTUDANTE")
        self.perfil = PerfilEstudante.objects.create(
            utilizador=self.u, numero_estudante="A1", curso=curso, ano_frequencia=3,
            media_geral=Decimal("15"), registo_estado=PerfilEstudante.Registo.PENDENTE,
        )
        self.client.force_login(self.u)

    def test_menu_lateral_ja_nao_tem_documentos_nem_perfil(self):
        html = self.client.get(reverse("estudantes:painel")).content.decode()
        self.assertNotIn(f'href="{reverse("estudantes:documentos")}"', html)
        self.assertNotIn(reverse("estudantes:perfil"), html)

    def test_painel_lista_documentos(self):
        doc = self.perfil.guardar_documento(
            "DECLARACAO", SimpleUploadedFile("n.pdf", b"%PDF-1.4 a")
        )
        try:
            html = self.client.get(reverse("estudantes:painel")).content.decode()
            self.assertIn("Os meus documentos", html)
            self.assertIn(reverse("estudantes:documento", args=[doc.pk]), html)
        finally:
            doc.ficheiro.delete(save=False)
