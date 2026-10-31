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
        for estado in ("TESTE", "ENTREVISTA", "PROPOSTA", "APROVADO"):
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

    def test_paginas_renderizam_com_o_novo_layout(self):
        self.assertEqual(self.client.get(reverse("contas:publica")).status_code, 200)
        self.assertEqual(self.client.get(reverse("contas:entrar")).status_code, 200)
        self.assertEqual(self.client.get(reverse("contas:registo_estudante")).status_code, 200)

        paineis = (
            (self.admin, "relatorios:painel"),
            (self.u_aluno, "estudantes:painel"),
            (self.u_emp, "empresas:painel"),
        )
        for utilizador, painel in paineis:
            self.client.force_login(utilizador)
            resposta = self.client.get(reverse(painel))
            self.assertContains(resposta, "SIGEST")
            self.assertContains(resposta, "vendor/bootstrap/css/bootstrap.min.css")

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

from apps.core.models import Notificacao  # noqa: E402


class RegistoEValidacaoDeEstudantesTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nome="Engenharia Informatica", sigla="EI")
        self.coord = User.objects.create_user("coord", "coord@t.ao", "x", tipo="COORDENADOR")

    def _registar(self, ficheiro_bi=None, username="novo"):
        return self.client.post(
            reverse("contas:registo_estudante"),
            {
                "first_name": "Ana", "last_name": "Silva", "numero_estudante": "N1",
                "curso": self.curso.pk, "ano_frequencia": 3, "media_geral": "15",
                "username": username, "email": f"{username}@t.ao",
                "password1": "Palavra-passe-segura-9", "password2": "Palavra-passe-segura-9",
                "declaracao_notas": SimpleUploadedFile("notas.pdf", b"%PDF-1.4 teste"),
                "bilhete_identidade": ficheiro_bi
                or SimpleUploadedFile("bi.pdf", b"%PDF-1.4 teste"),
            },
        )

    def _limpar_ficheiros(self, perfil):
        for documento in perfil.documentos.all():
            self.addCleanup(documento.ficheiro.delete, save=False)

    def test_registo_fica_pendente_com_documentos_e_sem_elegibilidade(self):
        resposta = self._registar()
        self.assertEqual(resposta.status_code, 302)
        perfil = PerfilEstudante.objects.get(numero_estudante="N1")
        self._limpar_ficheiros(perfil)
        self.assertEqual(perfil.registo_estado, PerfilEstudante.Registo.PENDENTE)
        self.assertEqual(perfil.documentos.count(), 2)
        self.assertFalse(perfil.elegivel)
        self.assertTrue(Notificacao.objects.filter(destinatario=self.coord).exists())

    def test_ficheiro_com_conteudo_falso_e_recusado(self):
        falso = SimpleUploadedFile("bi.pdf", b"MZ isto nao e um pdf")
        resposta = self._registar(ficheiro_bi=falso)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(User.objects.filter(username="novo").exists())

    def test_coordenador_aprova_e_estudante_fica_elegivel(self):
        self._registar()
        perfil = PerfilEstudante.objects.get(numero_estudante="N1")
        self._limpar_ficheiros(perfil)
        self.client.force_login(self.coord)
        self.client.post(reverse("relatorios:aprovar_estudante", args=[perfil.pk]))
        perfil.refresh_from_db()
        self.assertEqual(perfil.registo_estado, PerfilEstudante.Registo.APROVADO)
        self.assertEqual(perfil.registo_decidido_por, self.coord)
        self.assertIsNotNone(perfil.registo_decidido_em)
        self.assertTrue(perfil.elegivel)

    def test_devolver_exige_motivo_e_estudante_pode_corrigir(self):
        self._registar()
        perfil = PerfilEstudante.objects.get(numero_estudante="N1")
        self._limpar_ficheiros(perfil)
        self.client.force_login(self.coord)
        self.client.post(reverse("relatorios:devolver_estudante", args=[perfil.pk]), {"motivo": "  "})
        perfil.refresh_from_db()
        self.assertEqual(perfil.registo_estado, PerfilEstudante.Registo.PENDENTE)

        self.client.post(reverse("relatorios:devolver_estudante", args=[perfil.pk]), {"motivo": "BI ilegível."})
        perfil.refresh_from_db()
        self.assertEqual(perfil.registo_estado, PerfilEstudante.Registo.DEVOLVIDO)

        self.client.force_login(perfil.utilizador)
        novo = SimpleUploadedFile("bi2.pdf", b"%PDF-1.4 novo")
        self.client.post(reverse("estudantes:documentos"), {"bilhete_identidade": novo})
        perfil.refresh_from_db()
        self._limpar_ficheiros(perfil)
        self.assertEqual(perfil.registo_estado, PerfilEstudante.Registo.PENDENTE)

    def test_documento_so_abre_ao_dono_e_a_gestao(self):
        self._registar()
        perfil = PerfilEstudante.objects.get(numero_estudante="N1")
        self._limpar_ficheiros(perfil)
        documento = perfil.documentos.first()
        url = reverse("estudantes:documento", args=[documento.pk])

        outro = User.objects.create_user("outro", "outro@t.ao", "x", tipo="ESTUDANTE")
        PerfilEstudante.objects.create(
            utilizador=outro, numero_estudante="N2", curso=self.curso,
            ano_frequencia=3, media_geral=Decimal("15"),
        )
        empresa = User.objects.create_user("emp9", "emp9@t.ao", "x", tipo="EMPRESA")

        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        for utilizador, esperado in ((outro, 403), (empresa, 403), (perfil.utilizador, 200), (self.coord, 200)):
            self.client.force_login(utilizador)
            resposta = self.client.get(url)
            self.assertEqual(resposta.status_code, esperado, utilizador.username)
            if esperado == 200:
                if getattr(resposta, "streaming", False):
                    b"".join(resposta.streaming_content)

    def test_estudante_nao_valida_registos(self):
        self._registar()
        perfil = PerfilEstudante.objects.get(numero_estudante="N1")
        self._limpar_ficheiros(perfil)
        resposta = self.client.post(reverse("relatorios:aprovar_estudante", args=[perfil.pk]))
        self.assertEqual(resposta.status_code, 403)
        perfil.refresh_from_db()
        self.assertEqual(perfil.registo_estado, PerfilEstudante.Registo.PENDENTE)
from django.contrib.auth import authenticate, get_user_model  # noqa: E402
from django.test import TestCase  # noqa: E402

from apps.contas.forms import EntrarForm  # noqa: E402


class LoginPorEmailTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.u = self.User.objects.create_user("ana", "Ana@Teste.ao", "Segredo#123", tipo="ESTUDANTE")

    def test_entra_com_email_sem_distinguir_maiusculas(self):
        self.assertEqual(authenticate(username="ana@TESTE.ao", password="Segredo#123"), self.u)

    def test_nome_de_utilizador_ja_nao_serve(self):
        self.assertIsNone(authenticate(username="ana", password="Segredo#123"))

    def test_palavra_passe_errada_e_conta_inactiva(self):
        self.assertIsNone(authenticate(username="ana@teste.ao", password="errada"))
        self.u.is_active = False
        self.u.save()
        self.assertIsNone(authenticate(username="ana@teste.ao", password="Segredo#123"))

    def test_formulario_de_entrada(self):
        bom = EntrarForm(data={"username": "ANA@teste.ao", "password": "Segredo#123"})
        self.assertTrue(bom.is_valid())
        self.assertEqual(bom.get_user(), self.u)
        mau = EntrarForm(data={"username": "ana", "password": "Segredo#123"})
        self.assertFalse(mau.is_valid())
        self.assertIn("incorretos", str(mau.errors))

    def test_orientador_nao_aceita_email_repetido(self):
        from apps.empresas.forms import OrientadorForm

        dados = {
            "first_name": "Rui", "last_name": "Silva", "cargo": "", "username": "rui",
            "email": "ANA@teste.ao", "password1": "Zx!kd83#Qpw", "password2": "Zx!kd83#Qpw",
        }
        repetido = OrientadorForm(data=dados, empresa=None)
        self.assertFalse(repetido.is_valid())
        self.assertIn("email", repetido.errors)
        dados["email"] = "rui@teste.ao"
        self.assertTrue(OrientadorForm(data=dados, empresa=None).is_valid())


class RotuloEntrarTests(TestCase):
    def test_pagina_de_entrada_pede_email(self):
        resposta = self.client.get("/entrar/")
        self.assertContains(resposta, "Email")
        self.assertNotContains(resposta, "Nome de utilizador")
