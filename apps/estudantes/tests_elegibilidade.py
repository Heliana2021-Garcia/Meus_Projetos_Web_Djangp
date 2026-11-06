from decimal import Decimal

from django.test import SimpleTestCase

from .models import PerfilEstudante

R = PerfilEstudante.Registo


def perfil(registo=R.APROVADO, ano=3, media="15.00"):
    return PerfilEstudante(
        registo_estado=registo, ano_frequencia=ano, media_geral=Decimal(media)
    )


class MotivosInelegibilidadeTests(SimpleTestCase):
    """Teste de caixa branca (metodo do caminho basico), V(G) = 4.

    Nos: 1 inicio | 2 registo | 3 motivo registo | 4 ano | 5 motivo ano |
         6 media | 7 motivo media | 8 retorno.
    """

    def test_caminho_1_elegivel(self):
        # 1-2-4-6-8
        p = perfil(R.APROVADO, 3, "15.00")
        self.assertEqual(p.motivos_inelegibilidade, [])
        self.assertTrue(p.elegivel)

    def test_caminho_2_registo_pendente(self):
        # 1-2-3-4-6-8
        p = perfil(R.PENDENTE, 3, "15.00")
        motivos = p.motivos_inelegibilidade
        self.assertEqual(len(motivos), 1)
        self.assertIn("validado pela coord", motivos[0])
        self.assertFalse(p.elegivel)

    def test_caminho_3_ano_insuficiente(self):
        # 1-2-4-5-6-8
        p = perfil(R.APROVADO, 2, "15.00")
        motivos = p.motivos_inelegibilidade
        self.assertEqual(len(motivos), 1)
        self.assertIn("ano ou superior", motivos[0])
        self.assertFalse(p.elegivel)

    def test_caminho_4_media_insuficiente(self):
        # 1-2-4-6-7-8
        p = perfil(R.APROVADO, 3, "12.00")
        motivos = p.motivos_inelegibilidade
        self.assertEqual(len(motivos), 1)
        self.assertIn("pelo menos 14", motivos[0])
        self.assertFalse(p.elegivel)

    def test_valor_limite_media_14_e_elegivel(self):
        # caso complementar: a regra exige "pelo menos" 14 valores
        p = perfil(R.APROVADO, 3, "14.00")
        self.assertEqual(p.motivos_inelegibilidade, [])

    def test_condicoes_acumuladas(self):
        # caso complementar: as tres condicoes falham em simultaneo
        p = perfil(R.PENDENTE, 2, "12.00")
        self.assertEqual(len(p.motivos_inelegibilidade), 3)