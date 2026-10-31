from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse


def _url():
    for nome in ("relatorios:relatorio_gestao", "relatorio_gestao"):
        try:
            return reverse(nome)
        except NoReverseMatch:
            continue
    raise AssertionError("rota relatorio_gestao nao encontrada")


class RelatorioGestaoTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.coord = U.objects.create_user("coord", "coord@t.ao", "Segredo#123", tipo="COORDENADOR")
        self.estudante = U.objects.create_user("est", "est@t.ao", "Segredo#123", tipo="ESTUDANTE")
        self.url = _url()

    def test_so_a_gestao_acede(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.estudante)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_todas_as_entidades_abrem_para_o_coordenador(self):
        self.client.force_login(self.coord)
        for chave in ("estudantes", "empresas", "vagas", "candidaturas"):
            resposta = self.client.get(self.url, {"entidade": chave})
            self.assertEqual(resposta.status_code, 200, chave)
            self.assertContains(resposta, "Sem registos")

    def test_valores_invalidos_sao_ignorados(self):
        self.client.force_login(self.coord)
        resposta = self.client.get(self.url, {
            "entidade": "xpto", "de": "2026-13-45", "ate": "abc",
            "estado": "qualquer", "curso": "abc", "empresa": "9999"})
        self.assertEqual(resposta.status_code, 200)

    def test_exportacao_csv_e_pdf(self):
        self.client.force_login(self.coord)
        csv_ = self.client.get(self.url, {"entidade": "candidaturas", "formato": "csv"})
        self.assertTrue(csv_["Content-Type"].startswith("text/csv"))
        self.assertIn("Estudante", csv_.content.decode("utf-8-sig"))
        pdf = self.client.get(self.url, {"entidade": "vagas", "formato": "pdf"})
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))