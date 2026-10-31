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
        candidatura.mover_para("TESTE")
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

        c1.mover_para("TESTE")
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
    def test_entrevista_exige_passar_pelo_teste_psicotecnico(self):
        c1 = Candidatura.objects.create(estudante=self.aluno, vaga=self.vaga1)
        with self.assertRaises(ValidationError):
            c1.mover_para("ENTREVISTA")
        c1.mover_para("TESTE")
        c1.mover_para("ENTREVISTA")
        self.assertEqual(c1.estado, Candidatura.Estado.ENTREVISTA)

from decimal import Decimal  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402
from django.test import TestCase  # noqa: E402

from apps.candidaturas.models import Candidatura  # noqa: E402
from apps.empresas.models import Empresa  # noqa: E402
from apps.estudantes.models import Curso, PerfilEstudante  # noqa: E402
from apps.vagas.models import Vaga  # noqa: E402


class FasesConfiguraveisTests(TestCase):
    def setUp(self):
        User = get_user_model()
        curso = Curso.objects.create(nome="Engenharia", sigla="EN")
        aluno = User.objects.create_user("fa1", "fa1@t.ao", "x", tipo="ESTUDANTE")
        self.aluno = PerfilEstudante.objects.create(
            utilizador=aluno, numero_estudante="F1", curso=curso,
            ano_frequencia=3, media_geral=Decimal("15"),
        )
        dono = User.objects.create_user("fe1", "fe1@t.ao", "x", tipo="EMPRESA")
        self.empresa = Empresa.objects.create(utilizador=dono, nome="E", nif="2000000001")
        self.empresa.validar_nif()

    def _candidatura(self, **fases):
        vaga = Vaga.objects.create(empresa=self.empresa, titulo="V", **fases)
        vaga.publicar()
        return Candidatura.objects.create(estudante=self.aluno, vaga=vaga)

    def test_por_omissao_mantem_teste_e_entrevista(self):
        c = self._candidatura()
        self.assertEqual(c.sequencia(), ["PENDENTE", "TESTE", "ENTREVISTA", "PROPOSTA", "APROVADO"])
        for destino in ("TESTE", "ENTREVISTA", "PROPOSTA"):
            c.mover_para(destino)
        self.assertEqual(c.estado, "PROPOSTA")

    def test_sem_fases_opcionais_vai_direto_para_a_decisao_final(self):
        c = self._candidatura(fase_teste=False, fase_entrevista=False)
        self.assertEqual(c.sequencia(), ["PENDENTE", "PROPOSTA", "APROVADO"])
        self.assertEqual(c.transicoes_permitidas, ["PROPOSTA", "REJEITADO"])
        with self.assertRaises(ValidationError):
            c.mover_para("TESTE")
        c.mover_para("PROPOSTA")
        c.mover_para("APROVADO")
        self.assertEqual(c.estado, "APROVADO")

    def test_analise_do_curriculo_fica_entre_o_teste_e_a_entrevista(self):
        c = self._candidatura(fase_curriculo=True)
        self.assertEqual(
            c.sequencia(), ["PENDENTE", "TESTE", "CURRICULO", "ENTREVISTA", "PROPOSTA", "APROVADO"]
        )
        with self.assertRaises(ValidationError):
            c.mover_para("CURRICULO")  # tem de passar primeiro o teste
        c.mover_para("TESTE")
        with self.assertRaises(ValidationError):
            c.mover_para("ENTREVISTA")  # nao salta a analise do curriculo
        c.mover_para("CURRICULO")
        c.mover_para("ENTREVISTA")
        self.assertEqual(c.estado, "ENTREVISTA")

    def test_etapas_mostram_feita_atual_e_futura(self):
        c = self._candidatura()
        c.mover_para("TESTE")
        situacoes = [(e["rotulo"], e["situacao"]) for e in c.etapas]
        self.assertEqual(situacoes[0], ("Candidatura recebida", "feita"))
        self.assertEqual(situacoes[1], ("Teste psicotécnico", "atual"))
        self.assertEqual(situacoes[2][1], "futura")

    def test_rejeitar_continua_a_exigir_feedback(self):
        c = self._candidatura()
        with self.assertRaises(ValidationError):
            c.mover_para("REJEITADO", "  ")
        c.mover_para("REJEITADO", "Perfil não adequado.")
        self.assertEqual(c.etapas, [])

from django.test import override_settings  # noqa: E402
from django.urls import reverse  # noqa: E402

from apps.empresas.models import Orientador  # noqa: E402


class EstagioActivoTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.curso = Curso.objects.create(nome="Engenharia", sigla="EN")
        self.empresa, self.dono = self._empresa("ea", "3000000001")
        self.outra_empresa, self.outro_dono = self._empresa("eb", "3000000002")
        self.orientador = self._orientador("oa", self.empresa)
        self.alheio = self._orientador("ob", self.outra_empresa)
        self.vaga = Vaga.objects.create(
            empresa=self.empresa, titulo="V", numero_vagas=3,
            fase_teste=False, fase_entrevista=False, duracao_meses=3,
        )
        self.vaga.publicar()

    def _empresa(self, nome, nif):
        dono = self.User.objects.create_user(nome, f"{nome}@t.ao", "x", tipo="EMPRESA")
        empresa = Empresa.objects.create(utilizador=dono, nome=nome, nif=nif)
        empresa.validar_nif()
        return empresa, dono

    def _orientador(self, nome, empresa):
        utilizador = self.User.objects.create_user(nome, f"{nome}@t.ao", "x", tipo="ORIENTADOR")
        return Orientador.objects.create(utilizador=utilizador, empresa=empresa)

    def _aprovada(self, numero):
        utilizador = self.User.objects.create_user(f"al{numero}", f"al{numero}@t.ao", "x", tipo="ESTUDANTE")
        perfil = PerfilEstudante.objects.create(
            utilizador=utilizador, numero_estudante=numero, curso=self.curso,
            ano_frequencia=3, media_geral=Decimal("15"),
        )
        c = Candidatura.objects.create(estudante=perfil, vaga=self.vaga)
        c.mover_para("PROPOSTA")
        c.mover_para("APROVADO")
        return c

    def test_orientador_tem_de_ser_da_empresa_de_acolhimento(self):
        c = self._aprovada("E1")
        self.assertEqual(c.estagio_estado, "POR_INICIAR")
        with self.assertRaises(ValidationError):
            c.atribuir_orientador(self.alheio)
        c.atribuir_orientador(self.orientador)
        self.assertEqual(c.orientador, self.orientador)

    @override_settings(MAX_ESTAGIOS_POR_ORIENTADOR=1)
    def test_limite_de_estagios_por_orientador(self):
        primeira = self._aprovada("E2")
        segunda = self._aprovada("E3")
        primeira.atribuir_orientador(self.orientador)
        with self.assertRaises(ValidationError):
            segunda.atribuir_orientador(self.orientador)

    def test_inicio_depende_do_orientador_e_das_duas_confirmacoes(self):
        c = self._aprovada("E4")
        with self.assertRaises(ValidationError):
            c.confirmar_inicio(self.dono)  # sem orientador
        c.atribuir_orientador(self.orientador)
        c.confirmar_inicio(self.dono)
        self.assertEqual(c.estagio_estado, "POR_INICIAR")
        with self.assertRaises(ValidationError):
            c.confirmar_inicio(self.dono)  # empresa so confirma uma vez
        with self.assertRaises(ValidationError):
            c.confirmar_inicio(self.outro_dono)  # outra empresa nao pode
        c.confirmar_inicio(c.estudante.utilizador)
        self.assertEqual(c.estagio_estado, "EM_CURSO")
        self.assertIsNotNone(c.data_inicio)
        self.assertEqual(c.data_fim, Candidatura._somar_meses(c.data_inicio, 3))

    def test_interromper_exige_motivo_e_liberta_o_estudante(self):
        c = self._aprovada("E5")
        self.assertEqual(c.estudante.estado, PerfilEstudante.Estado.OCUPADO)
        with self.assertRaises(ValidationError):
            c.interromper(self.dono, "  ")
        c.interromper(self.dono, "Fim antecipado do contrato.")
        c.estudante.refresh_from_db()
        self.assertEqual(c.estagio_estado, "INTERROMPIDO")
        self.assertEqual(c.interrompido_por, self.dono)
        self.assertEqual(c.estudante.estado, PerfilEstudante.Estado.DISPONIVEL)
        with self.assertRaises(ValidationError):
            c.concluir_estagio("15")

    def test_painel_do_orientador_mostra_so_os_seus_estagiarios(self):
        c = self._aprovada("E6")
        c.atribuir_orientador(self.orientador)
        self.client.force_login(self.orientador.utilizador)
        resposta = self.client.get(reverse("empresas:painel_orientador"))
        self.assertContains(resposta, "E6")
        self.client.force_login(self.alheio.utilizador)
        resposta = self.client.get(reverse("empresas:painel_orientador"))
        self.assertNotContains(resposta, "E6")

    def test_permissoes_nas_accoes_de_estagio(self):
        c = self._aprovada("E7")
        url = reverse("candidaturas:atribuir_orientador", args=[c.pk])
        dados = {"orientador": self.orientador.pk}

        self.client.force_login(c.estudante.utilizador)
        self.assertEqual(self.client.post(url, dados).status_code, 403)
        self.client.force_login(self.outro_dono)
        self.assertEqual(self.client.post(url, dados).status_code, 404)

        self.client.force_login(self.dono)
        self.client.post(url, dados)
        c.refresh_from_db()
        self.assertEqual(c.orientador, self.orientador)

        self.client.force_login(self.orientador.utilizador)
        self.assertEqual(
            self.client.post(reverse("candidaturas:interromper", args=[c.pk]), {"motivo": "x"}).status_code, 403
        )

from datetime import timedelta  # noqa: E402

from django.utils import timezone  # noqa: E402

from .models import RegistoDiario, RelatorioEstagio  # noqa: E402


class AcompanhamentoTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.curso = Curso.objects.create(nome="Engenharia", sigla="EN")
        self.dono = self.User.objects.create_user("emp", "emp@t.ao", "x", tipo="EMPRESA")
        self.empresa = Empresa.objects.create(utilizador=self.dono, nome="emp", nif="4000000001")
        self.empresa.validar_nif()
        self.orientador = self._orientador("oa")
        self.outro = self._orientador("ob")
        self.vaga = Vaga.objects.create(
            empresa=self.empresa, titulo="V", numero_vagas=2,
            fase_teste=False, fase_entrevista=False, duracao_meses=3,
        )
        self.vaga.publicar()
        aluno = self.User.objects.create_user("al1", "al1@t.ao", "x", tipo="ESTUDANTE")
        perfil = PerfilEstudante.objects.create(
            utilizador=aluno, numero_estudante="A1", curso=self.curso,
            ano_frequencia=3, media_geral=Decimal("15"),
        )
        self.c = Candidatura.objects.create(estudante=perfil, vaga=self.vaga)
        self.c.mover_para("PROPOSTA")
        self.c.mover_para("APROVADO")
        self.aluno = aluno
        self.hoje = timezone.localdate()

    def _orientador(self, nome):
        utilizador = self.User.objects.create_user(nome, f"{nome}@t.ao", "x", tipo="ORIENTADOR")
        return Orientador.objects.create(utilizador=utilizador, empresa=self.empresa)

    def _iniciar(self):
        self.c.atribuir_orientador(self.orientador)
        self.c.confirmar_inicio(self.dono)
        self.c.confirmar_inicio(self.aluno)
        self.c.refresh_from_db()

    def _registo(self):
        self._iniciar()
        return RegistoDiario.objects.create(candidatura=self.c, data=self.hoje, descricao="x")

    def test_diario_so_com_estagio_em_curso_e_datas_validas(self):
        url = reverse("candidaturas:diario")
        dados = {"data": self.hoje.isoformat(), "descricao": "Configurei o servidor."}
        self.client.force_login(self.aluno)
        self.client.post(url, dados)
        self.assertEqual(RegistoDiario.objects.count(), 0)  # estagio ainda nao iniciou
        self._iniciar()
        self.client.post(url, dados)
        self.assertEqual(RegistoDiario.objects.count(), 1)
        self.client.post(url, dados)  # data repetida
        self.assertEqual(RegistoDiario.objects.count(), 1)
        futuro = {**dados, "data": (self.hoje + timedelta(days=1)).isoformat()}
        self.client.post(url, futuro)
        self.assertEqual(RegistoDiario.objects.count(), 1)

    def test_validacao_correccao_e_protecao_do_registo_validado(self):
        r = self._registo()
        decidir = reverse("candidaturas:decidir", args=["registo", r.pk])
        editar = reverse("candidaturas:registo_editar", args=[r.pk])
        dados = {"data": self.hoje.isoformat(), "descricao": "melhor"}

        self.client.force_login(self.orientador.utilizador)
        self.client.post(decidir, {"acao": "corrigir", "comentario": ""})
        r.refresh_from_db()
        self.assertEqual(r.estado, "SUBMETIDO")  # correccao exige comentario
        self.client.post(decidir, {"acao": "corrigir", "comentario": "Falta detalhe."})
        r.refresh_from_db()
        self.assertEqual(r.estado, "CORRECAO")

        self.client.force_login(self.aluno)
        self.client.post(editar, dados)
        r.refresh_from_db()
        self.assertEqual((r.estado, r.descricao), ("SUBMETIDO", "melhor"))

        self.client.force_login(self.orientador.utilizador)
        self.client.post(decidir, {"acao": "validar"})
        r.refresh_from_db()
        self.assertEqual(r.estado, "VALIDADO")
        self.assertEqual(r.validado_por, self.orientador.utilizador)

        self.client.force_login(self.aluno)
        self.assertEqual(self.client.post(editar, {**dados, "descricao": "alterado"}).status_code, 404)
        r.refresh_from_db()
        self.assertEqual(r.descricao, "melhor")

    def test_so_o_orientador_atribuido_decide(self):
        r = self._registo()
        url = reverse("candidaturas:decidir", args=["registo", r.pk])
        self.client.force_login(self.outro.utilizador)
        self.assertEqual(self.client.post(url, {"acao": "validar"}).status_code, 404)
        self.client.force_login(self.aluno)
        self.assertEqual(self.client.post(url, {"acao": "validar"}).status_code, 403)
        r.refresh_from_db()
        self.assertEqual(r.estado, "SUBMETIDO")

    def test_relatorio_submetido_validado_e_bloqueado(self):
        self._iniciar()
        url = reverse("candidaturas:relatorio", args=["final"])
        self.client.force_login(self.aluno)
        self.client.post(url, {"titulo": "Relatório final", "conteudo": "Texto."})
        rel = RelatorioEstagio.objects.get(candidatura=self.c)
        self.assertEqual(rel.tipo, "FINAL")
        self.client.force_login(self.orientador.utilizador)
        self.client.post(reverse("candidaturas:decidir", args=["relatorio", rel.pk]), {"acao": "validar"})
        rel.refresh_from_db()
        self.assertEqual(rel.estado, "VALIDADO")
        self.client.force_login(self.aluno)
        self.client.post(url, {"titulo": "Outro", "conteudo": "Alterado."})
        rel.refresh_from_db()
        self.assertEqual(rel.conteudo, "Texto.")

    def test_acompanhar_so_para_quem_pode(self):
        self._iniciar()
        url = reverse("candidaturas:acompanhar", args=[self.c.pk])
        self.client.force_login(self.outro.utilizador)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.orientador.utilizador)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.dono)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.aluno)
        self.assertEqual(self.client.get(url).status_code, 403)

from . import servicos_avaliacao  # noqa: E402
from .models import Avaliacao  # noqa: E402


class AvaliacaoTests(TestCase):
    setUp = AcompanhamentoTests.setUp
    _orientador = AcompanhamentoTests._orientador
    _iniciar = AcompanhamentoTests._iniciar

    def _coordenador(self):
        return self.User.objects.create_user("coord", "coord@t.ao", "x", tipo="COORDENADOR")

    def _avaliar(self, papel, valor, comentario=""):
        v = Decimal(str(valor))
        return Avaliacao.objects.create(
            candidatura=self.c, papel=papel, objectivos=v, qualidade=v, responsabilidade=v,
            assiduidade=v, competencias=v, comentario=comentario,
        )

    def _quatro(self, comentario_empresa=""):
        self._avaliar("EMPRESA", 16, comentario_empresa)
        self._avaliar("ORIENTADOR", 14)
        self._avaliar("ESTUDANTE", 18)
        self._avaliar("COORDENADOR", 12)

    def _preparar_conclusao(self):
        self._iniciar()
        RegistoDiario.objects.create(
            candidatura=self.c, data=self.hoje, descricao="x", estado="VALIDADO"
        )
        RelatorioEstagio.objects.create(
            candidatura=self.c, tipo="FINAL", titulo="Final", conteudo="x", estado="VALIDADO"
        )
        self._quatro()

    def test_nota_final_e_media_pesada(self):
        self._iniciar()
        self._avaliar("EMPRESA", 16)
        self.assertIsNone(servicos_avaliacao.nota_final(self.c))  # faltam avaliacoes
        self._avaliar("ORIENTADOR", 14)
        self._avaliar("ESTUDANTE", 18)
        self._avaliar("COORDENADOR", 12)
        # (16*30 + 14*30 + 18*10 + 12*30) / 100
        self.assertEqual(servicos_avaliacao.nota_final(self.c), Decimal("14.40"))

    def test_conclusao_bloqueada_enquanto_faltam_condicoes(self):
        self._iniciar()
        self.assertTrue(servicos_avaliacao.impedimentos_conclusao(self.c))
        self.client.force_login(self._coordenador())
        self.client.post(reverse("candidaturas:validar_conclusao", args=[self.c.pk]))
        self.c.refresh_from_db()
        self.assertIsNone(self.c.concluida_em)

    def test_conclusao_calcula_nota_e_liberta_o_estudante(self):
        self._preparar_conclusao()
        self.assertEqual(servicos_avaliacao.impedimentos_conclusao(self.c), [])
        self.client.force_login(self._coordenador())
        self.client.post(reverse("candidaturas:validar_conclusao", args=[self.c.pk]))
        self.c.refresh_from_db()
        self.c.estudante.refresh_from_db()
        self.assertIsNotNone(self.c.concluida_em)
        self.assertAlmostEqual(float(self.c.avaliacao_final), 14.4, places=1)
        self.assertEqual(self.c.estudante.estado, PerfilEstudante.Estado.DISPONIVEL)
        self.assertEqual(self.c.estagio_estado, "CONCLUIDO")

    def test_permissoes_da_avaliacao(self):
        self._preparar_conclusao()
        self.client.force_login(self.outro.utilizador)
        self.assertEqual(self.client.get(reverse("candidaturas:avaliacao", args=[self.c.pk])).status_code, 404)
        self.client.force_login(self.aluno)
        resposta = self.client.post(reverse("candidaturas:validar_conclusao", args=[self.c.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.c.refresh_from_db()
        self.assertIsNone(self.c.concluida_em)

    def test_estudante_so_ve_a_sua_avaliacao_ate_ao_fim(self):
        self._iniciar()
        self._quatro(comentario_empresa="SEGREDO-EMPRESA")
        url = reverse("candidaturas:avaliacao", args=[self.c.pk])
        self.client.force_login(self.aluno)
        self.assertNotContains(self.client.get(url), "SEGREDO-EMPRESA")
        self.c.concluida_em = timezone.now()
        self.c.save()
        self.assertContains(self.client.get(url), "SEGREDO-EMPRESA")

    def test_avaliar_pela_vista_valida_intervalo_e_papel(self):
        self._iniciar()
        url = reverse("candidaturas:avaliar", args=[self.c.pk])
        dados = {nome: "15" for nome, _ in Avaliacao.CRITERIOS}
        self.client.force_login(self.orientador.utilizador)
        self.client.post(url, {**dados, "qualidade": "25"})
        self.assertEqual(Avaliacao.objects.count(), 0)  # fora de 0-20
        self.client.post(url, dados)
        avaliacao = Avaliacao.objects.get()
        self.assertEqual(avaliacao.papel, "ORIENTADOR")
        self.assertEqual(avaliacao.nota, Decimal("15.00"))
from apps.relatorios import filtros_estagios  # noqa: E402


class DocumentosEFiltrosTests(TestCase):
    setUp = AcompanhamentoTests.setUp
    _orientador = AcompanhamentoTests._orientador
    _iniciar = AcompanhamentoTests._iniciar

    def _concluir(self):
        self._iniciar()
        self.c.concluida_em = timezone.now()
        self.c.avaliacao_final = Decimal("14.40")
        self.c.save()

    def _coordenador(self):
        return self.User.objects.create_user("coord", "coord@t.ao", "x", tipo="COORDENADOR")

    def test_certificado_so_depois_de_concluido(self):
        url = reverse("candidaturas:certificado", args=[self.c.pk])
        self._iniciar()
        self.client.force_login(self.aluno)
        antes = self.client.get(url)
        self.assertEqual(antes.status_code, 302)
        self.c.concluida_em = timezone.now()
        self.c.avaliacao_final = Decimal("14.40")
        self.c.save()
        depois = self.client.get(url)
        self.assertEqual(depois.status_code, 200)
        self.assertEqual(depois["Content-Type"], "application/pdf")
        self.assertTrue(depois.content.startswith(b"%PDF"))

    def test_permissoes_do_certificado(self):
        self._concluir()
        url = reverse("candidaturas:certificado", args=[self.c.pk])
        self.client.force_login(self.outro.utilizador)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self._coordenador())
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_filtros_por_estado_e_modalidade(self):
        self.assertIn(self.c, filtros_estagios.filtrar({"estado": "POR_INICIAR"}))
        self.assertNotIn(self.c, filtros_estagios.filtrar({"estado": "EM_CURSO"}))
        self._iniciar()
        self.assertIn(self.c, filtros_estagios.filtrar({"estado": "EM_CURSO"}))
        self.assertNotIn(self.c, filtros_estagios.filtrar({"estado": "POR_INICIAR"}))
        self.assertIn(self.c, filtros_estagios.filtrar({"empresa": "emp"}))
        self.assertNotIn(self.c, filtros_estagios.filtrar({"empresa": "outra"}))
        outro_tipo = "PROFISSIONAL" if self.vaga.tipo_estagio == "CURRICULAR" else "CURRICULAR"
        self.assertNotIn(self.c, filtros_estagios.filtrar({"tipo": outro_tipo}))
        self.assertIn(self.c, filtros_estagios.filtrar({"de": "invalida"}))  # data invalida e ignorada

    def test_relatorio_de_gestao_e_exportacoes(self):
        self._iniciar()
        self.client.force_login(self.aluno)
        self.assertEqual(self.client.get(reverse("relatorios:relatorio_estagios")).status_code, 403)
        self.client.force_login(self._coordenador())
        ecra = self.client.get(reverse("relatorios:relatorio_estagios"), {"estado": "EM_CURSO"})
        self.assertContains(ecra, "A1")
        csv_resposta = self.client.get(reverse("relatorios:relatorio_estagios_csv"))
        self.assertIn("text/csv", csv_resposta["Content-Type"])
        self.assertIn("A1", csv_resposta.content.decode("utf-8"))
        pdf = self.client.get(reverse("relatorios:relatorio_estagios_pdf"), {"estado": "EM_CURSO"})
        self.assertTrue(pdf.content.startswith(b"%PDF"))
from apps.contas.models import Utilizador  # noqa: E402
from apps.core.models import RegistoDecisao  # noqa: E402


class AuditoriaEEfectivacaoTests(TestCase):
    setUp = AcompanhamentoTests.setUp
    _orientador = AcompanhamentoTests._orientador
    _iniciar = AcompanhamentoTests._iniciar
    _avaliar = AvaliacaoTests._avaliar
    _quatro = AvaliacaoTests._quatro
    _preparar_conclusao = AvaliacaoTests._preparar_conclusao

    def _coordenador(self):
        return self.User.objects.create_user("coord", "coord@t.ao", "x", tipo="COORDENADOR")

    def test_decisao_bem_sucedida_fica_registada(self):
        self._preparar_conclusao()
        coord = self._coordenador()
        self.client.force_login(coord)
        self.client.post(reverse("candidaturas:validar_conclusao", args=[self.c.pk]))
        registo = RegistoDecisao.objects.get()
        self.assertEqual(registo.utilizador, coord)
        self.assertEqual(registo.accao, "Conclusão do estágio validada")
        pagina = self.client.get(reverse("relatorios:decisoes"))
        self.assertContains(pagina, "Conclusão do estágio validada")

    def test_pedido_recusado_nao_fica_registado(self):
        self._iniciar()  # faltam avaliacoes e relatorio final: a conclusao e recusada
        self.client.force_login(self._coordenador())
        self.client.post(reverse("candidaturas:validar_conclusao", args=[self.c.pk]))
        self.assertEqual(RegistoDecisao.objects.count(), 0)

    def test_efectivacao_so_apos_conclusao_e_so_uma_vez(self):
        url = reverse("candidaturas:efectivacao", args=[self.c.pk])
        self._preparar_conclusao()
        self.client.force_login(self.dono)
        self.client.post(url, {"resultado": "sim"})
        self.c.refresh_from_db()
        self.assertIsNone(self.c.efectivado)  # ainda nao concluido

        servicos_avaliacao.concluir(self.c, self._coordenador())
        self.client.post(url, {"resultado": "sim"})
        self.c.refresh_from_db()
        self.assertIs(self.c.efectivado, True)
        self.client.post(url, {"resultado": "nao"})
        self.c.refresh_from_db()
        self.assertIs(self.c.efectivado, True)  # nao se altera

        self.client.force_login(self.aluno)
        self.assertEqual(self.client.post(url, {"resultado": "nao"}).status_code, 403)

    def test_paginas_protegidas_por_perfil(self):
        T = Utilizador.Tipo
        gestao = {T.ADMINISTRADOR, T.COORDENADOR}
        regras = [
            ("estudantes:painel", {T.ESTUDANTE}),
            ("estudantes:documentos", {T.ESTUDANTE}),
            ("candidaturas:minhas", {T.ESTUDANTE}),
            ("candidaturas:estagio", {T.ESTUDANTE}),
            ("candidaturas:diario", {T.ESTUDANTE}),
            ("candidaturas:relatorios", {T.ESTUDANTE}),
            ("empresas:painel", {T.EMPRESA}),
            ("empresas:orientadores", {T.EMPRESA}),
            ("candidaturas:estagios", {T.EMPRESA}),
            ("empresas:painel_orientador", {T.ORIENTADOR}),
            ("relatorios:painel", gestao),
            ("relatorios:estudantes_pendentes", gestao),
            ("relatorios:vagas_analise", gestao),
            ("relatorios:estagios", gestao),
            ("relatorios:relatorio_estagios", gestao),
            ("relatorios:decisoes", gestao),
        ]
        utilizadores = {
            tipo: self.User.objects.create_user(f"t_{tipo}", f"{tipo}@t.ao", "x", tipo=tipo)
            for tipo, _ in T.choices
        }
        for nome, permitidos in regras:
            url = reverse(nome)
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302, f"{nome} sem sessao")
            for tipo, utilizador in utilizadores.items():
                if tipo in permitidos:
                    continue
                self.client.force_login(utilizador)
                self.assertIn(self.client.get(url).status_code, (403, 404), f"{nome} / {tipo}")
from apps.contas.models import Utilizador  # noqa: E402
from apps.core.models import RegistoDecisao  # noqa: E402


class AuditoriaEEfectivacaoTests(TestCase):
    setUp = AcompanhamentoTests.setUp
    _orientador = AcompanhamentoTests._orientador
    _iniciar = AcompanhamentoTests._iniciar
    _avaliar = AvaliacaoTests._avaliar
    _quatro = AvaliacaoTests._quatro
    _preparar_conclusao = AvaliacaoTests._preparar_conclusao

    def _coordenador(self):
        return self.User.objects.create_user("coord", "coord@t.ao", "x", tipo="COORDENADOR")

    def test_decisao_bem_sucedida_fica_registada(self):
        self._preparar_conclusao()
        coord = self._coordenador()
        self.client.force_login(coord)
        self.client.post(reverse("candidaturas:validar_conclusao", args=[self.c.pk]))
        registo = RegistoDecisao.objects.get()
        self.assertEqual(registo.utilizador, coord)
        self.assertEqual(registo.accao, "Conclusão do estágio validada")
        pagina = self.client.get(reverse("relatorios:decisoes"))
        self.assertContains(pagina, "Conclusão do estágio validada")

    def test_pedido_recusado_nao_fica_registado(self):
        self._iniciar()  # faltam avaliacoes e relatorio final: a conclusao e recusada
        self.client.force_login(self._coordenador())
        self.client.post(reverse("candidaturas:validar_conclusao", args=[self.c.pk]))
        self.assertEqual(RegistoDecisao.objects.count(), 0)

    def test_efectivacao_so_apos_conclusao_e_so_uma_vez(self):
        url = reverse("candidaturas:efectivacao", args=[self.c.pk])
        self._preparar_conclusao()
        self.client.force_login(self.dono)
        self.client.post(url, {"resultado": "sim"})
        self.c.refresh_from_db()
        self.assertIsNone(self.c.efectivado)  # ainda nao concluido

        servicos_avaliacao.concluir(self.c, self._coordenador())
        self.client.post(url, {"resultado": "sim"})
        self.c.refresh_from_db()
        self.assertIs(self.c.efectivado, True)
        self.client.post(url, {"resultado": "nao"})
        self.c.refresh_from_db()
        self.assertIs(self.c.efectivado, True)  # nao se altera

        self.client.force_login(self.aluno)
        self.assertEqual(self.client.post(url, {"resultado": "nao"}).status_code, 403)

    def test_paginas_protegidas_por_perfil(self):
        T = Utilizador.Tipo
        gestao = {T.ADMINISTRADOR, T.COORDENADOR}
        regras = [
            ("estudantes:painel", {T.ESTUDANTE}),
            ("estudantes:documentos", {T.ESTUDANTE}),
            ("candidaturas:minhas", {T.ESTUDANTE}),
            ("candidaturas:estagio", {T.ESTUDANTE}),
            ("candidaturas:diario", {T.ESTUDANTE}),
            ("candidaturas:relatorios", {T.ESTUDANTE}),
            ("empresas:painel", {T.EMPRESA}),
            ("empresas:orientadores", {T.EMPRESA}),
            ("candidaturas:estagios", {T.EMPRESA}),
            ("empresas:painel_orientador", {T.ORIENTADOR}),
            ("relatorios:painel", gestao),
            ("relatorios:estudantes_pendentes", gestao),
            ("relatorios:vagas_analise", gestao),
            ("relatorios:estagios", gestao),
            ("relatorios:relatorio_estagios", gestao),
            ("relatorios:decisoes", gestao),
        ]
        utilizadores = {
            tipo: self.User.objects.create_user(f"t_{tipo}", f"{tipo}@t.ao", "x", tipo=tipo)
            for tipo, _ in T.choices
        }
        for nome, permitidos in regras:
            url = reverse(nome)
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302, f"{nome} sem sessao")
            for tipo, utilizador in utilizadores.items():
                if tipo in permitidos:
                    continue
                self.client.force_login(utilizador)
                self.assertIn(self.client.get(url).status_code, (403, 404), f"{nome} / {tipo}")
