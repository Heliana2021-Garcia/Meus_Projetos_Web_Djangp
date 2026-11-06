from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from . import servicos_avaliacao
from . import tests as base
from .models import AvaliacaoMensal, RegistoDiario


class BaseAvaliacao(TestCase):
    setUp = base.AcompanhamentoTests.setUp
    _orientador = base.AcompanhamentoTests._orientador
    _iniciar = base.AcompanhamentoTests._iniciar
    _coordenador = base.PreparacaoConclusao._coordenador
    _definir_inicio = base.PreparacaoConclusao._definir_inicio
    _mensais = base.PreparacaoConclusao._mensais
    _preparar_conclusao = base.PreparacaoConclusao._preparar_conclusao

    def _registo(self, dias=0, estado="SUBMETIDO", nota=None):
        return RegistoDiario.objects.create(
            candidatura=self.c, data=self.hoje - timedelta(days=dias),
            descricao="x", estado=estado, nota=nota,
        )

    def _decidir(self, utilizador, registo, **dados):
        self.client.force_login(utilizador)
        return self.client.post(reverse("candidaturas:decidir", args=["registo", registo.pk]), dados)

    def _enviar_mensal(self, nota="15", comentario="ok"):
        self.client.force_login(self.aluno)
        return self.client.post(
            reverse("candidaturas:avaliar_orientador"), {"nota": nota, "comentario": comentario}
        )


class NotaDoOrientadorTests(BaseAvaliacao):
    def test_nota_final_e_a_media_das_notas_dos_registos(self):
        self._iniciar()
        self.assertIsNone(servicos_avaliacao.nota_final(self.c))
        for dias, nota in ((1, "16"), (2, "14"), (3, "13")):
            self._registo(dias, "VALIDADO", Decimal(nota))
        self.assertEqual(servicos_avaliacao.nota_final(self.c), Decimal("14.33"))

    def test_orientador_da_a_nota_ao_validar(self):
        self._iniciar()
        r = self._registo()
        self._decidir(self.orientador.utilizador, r, acao="validar", nota="17.5", comentario="")
        r.refresh_from_db()
        self.assertEqual(r.estado, "VALIDADO")
        self.assertEqual(r.nota, Decimal("17.50"))

    def test_nota_fora_de_0_a_20_ou_em_falta_e_recusada(self):
        self._iniciar()
        r = self._registo()
        for valor in ("", "21", "-1", "abc"):
            self._decidir(self.orientador.utilizador, r, acao="validar", nota=valor, comentario="")
            r.refresh_from_db()
            self.assertEqual(r.estado, "SUBMETIDO", valor)
            self.assertIsNone(r.nota, valor)
        self._decidir(self.orientador.utilizador, r, acao="validar", nota="20", comentario="")
        r.refresh_from_db()
        self.assertEqual(r.estado, "VALIDADO")
        self.assertEqual(r.nota, Decimal("20"))

    def test_pedir_correccao_nao_exige_nota(self):
        self._iniciar()
        r = self._registo()
        self._decidir(self.orientador.utilizador, r, acao="corrigir", comentario="refazer")
        r.refresh_from_db()
        self.assertNotEqual(r.estado, "SUBMETIDO")
        self.assertIsNone(r.nota)


class ConclusaoPelaEmpresaTests(BaseAvaliacao):
    def _aprovar(self, utilizador):
        self.client.force_login(utilizador)
        return self.client.post(reverse("candidaturas:validar_conclusao", args=[self.c.pk]))

    def test_conclusao_bloqueada_enquanto_faltam_condicoes(self):
        self._iniciar()
        self.assertTrue(servicos_avaliacao.impedimentos_conclusao(self.c))
        self._aprovar(self.dono)
        self.c.refresh_from_db()
        self.assertIsNone(self.c.concluida_em)

    def test_empresa_aprova_e_a_nota_final_e_a_media(self):
        self._preparar_conclusao()
        self.assertEqual(servicos_avaliacao.impedimentos_conclusao(self.c), [])
        self._aprovar(self.dono)
        self.c.refresh_from_db()
        self.assertIsNotNone(self.c.concluida_em)
        self.assertEqual(self.c.avaliacao_final, Decimal("14.33"))
        self.assertEqual(self.c.estagio_estado, "CONCLUIDO")

    def test_so_depois_de_terminada_a_duracao(self):
        self._preparar_conclusao()
        self._definir_inicio(10, meses=3, fim=self.hoje + timedelta(days=20))
        self.assertTrue(servicos_avaliacao.impedimentos_conclusao(self.c))
        self._aprovar(self.dono)
        self.c.refresh_from_db()
        self.assertIsNone(self.c.concluida_em)

    def test_exige_todas_as_avaliacoes_mensais(self):
        self._preparar_conclusao()
        AvaliacaoMensal.objects.filter(candidatura=self.c, mes=3).delete()
        self.assertTrue(servicos_avaliacao.impedimentos_conclusao(self.c))
        self._aprovar(self.dono)
        self.c.refresh_from_db()
        self.assertIsNone(self.c.concluida_em)

    def test_coordenador_nao_avalia_nem_conclui(self):
        self._preparar_conclusao()
        coord = self._coordenador()
        self.assertEqual(self._aprovar(coord).status_code, 403)
        r = self._registo(10)
        self.assertEqual(
            self._decidir(coord, r, acao="validar", nota="15", comentario="").status_code, 403
        )
        r.refresh_from_db()
        self.assertEqual(r.estado, "SUBMETIDO")
        self.client.force_login(coord)
        resposta = self.client.get(reverse("candidaturas:avaliacao", args=[self.c.pk]))
        self.assertEqual(resposta.status_code, 200)


class AvaliacaoMensalDoOrientadorTests(BaseAvaliacao):
    def test_so_abre_aos_30_dias(self):
        self._iniciar()
        for dias, esperado in ((29, 0), (30, 1)):
            self._definir_inicio(dias, meses=3)
            self._enviar_mensal()
            self.assertEqual(AvaliacaoMensal.objects.filter(candidatura=self.c).count(), esperado, dias)

    def test_estagio_de_um_mes_abre_no_fim_da_duracao(self):
        self._iniciar()
        self._definir_inicio(10, meses=1, fim=self.hoje)
        self._enviar_mensal()
        self.assertEqual(AvaliacaoMensal.objects.filter(candidatura=self.c).count(), 1)

    def test_nota_mensal_fora_de_0_a_20_e_recusada(self):
        self._iniciar()
        self._definir_inicio(31)
        for valor in ("21", "-1"):
            self._enviar_mensal(nota=valor)
        self.assertEqual(AvaliacaoMensal.objects.count(), 0)

    def test_so_a_empresa_ve_o_comentario_do_aluno(self):
        self._iniciar()
        self._definir_inicio(31)
        self._enviar_mensal(nota="12", comentario="SEGREDO-ALUNO")
        self.assertEqual(AvaliacaoMensal.objects.count(), 1)
        url = reverse("candidaturas:avaliacao", args=[self.c.pk])
        self.client.force_login(self.dono)
        self.assertContains(self.client.get(url), "SEGREDO-ALUNO")
        self.client.force_login(self.orientador.utilizador)
        self.assertNotContains(self.client.get(url), "SEGREDO-ALUNO")
        self.client.force_login(self._coordenador())
        self.assertNotContains(self.client.get(url), "SEGREDO-ALUNO")
