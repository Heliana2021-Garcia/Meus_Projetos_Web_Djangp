from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.empresas.models import Empresa, Orientador
from apps.estudantes.models import Curso, PerfilEstudante

User = get_user_model()
SENHA = "Senha-Forte-2026"


class PerfilBase(TestCase):
    def setUp(self):
        curso = Curso.objects.create(nome="Engenharia Informatica", sigla="EI")
        self.u_aluno = User.objects.create_user(
            "aluno@t.ao", "aluno@t.ao", SENHA, tipo="ESTUDANTE", first_name="Ana", last_name="Silva"
        )
        self.aluno = PerfilEstudante.objects.create(
            utilizador=self.u_aluno, numero_estudante="A1", curso=curso,
            ano_frequencia=3, media_geral=Decimal("15"),
        )
        self.u_emp = User.objects.create_user("emp@t.ao", "emp@t.ao", SENHA, tipo="EMPRESA", first_name="Rui")
        self.empresa = Empresa.objects.create(utilizador=self.u_emp, nome="Emp", nif="1000000001")
        self.u_ori = User.objects.create_user("joao.ori", "ori@t.ao", SENHA, tipo="ORIENTADOR", first_name="Joao")
        self.orientador = Orientador.objects.create(utilizador=self.u_ori, empresa=self.empresa, cargo="Chefe")
        self.u_coord = User.objects.create_user("coord@t.ao", "coord@t.ao", SENHA, tipo="COORDENADOR")

    def conta(self, utilizador, **extra):
        dados = {
            "accao": "conta",
            "conta-first_name": utilizador.first_name or "Nome",
            "conta-last_name": utilizador.last_name or "Apelido",
            "conta-email": utilizador.email,
        }
        dados.update(extra)
        return dados


class MenuETests(PerfilBase):
    def test_anonimo_vai_para_o_login(self):
        for nome in ("contas:perfil", "contas:editar_perfil"):
            resposta = self.client.get(reverse(nome))
            self.assertEqual(resposta.status_code, 302)
            self.assertIn(reverse("contas:entrar"), resposta.url)

    def test_menu_tem_as_tres_opcoes(self):
        self.client.force_login(self.u_aluno)
        html = self.client.get(reverse("estudantes:painel")).content.decode()
        self.assertIn(reverse("contas:perfil"), html)
        self.assertIn(reverse("contas:editar_perfil"), html)
        self.assertIn("Sair", html)

    def test_todos_os_perfis_abrem_as_duas_paginas(self):
        for utilizador in (self.u_aluno, self.u_emp, self.u_ori, self.u_coord):
            self.client.force_login(utilizador)
            for nome in ("contas:perfil", "contas:editar_perfil"):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200, (utilizador, nome))

    def test_antiga_url_do_estudante_redirecciona(self):
        self.client.force_login(self.u_aluno)
        resposta = self.client.get(reverse("estudantes:perfil"))
        self.assertRedirects(resposta, reverse("contas:editar_perfil"), fetch_redirect_response=False)


class ContaTests(PerfilBase):
    def test_actualiza_nome_e_email_e_username(self):
        self.client.force_login(self.u_aluno)
        resposta = self.client.post(reverse("contas:editar_perfil"), self.conta(
            self.u_aluno, **{"conta-first_name": "Maria", "conta-email": "Maria@T.ao"}))
        self.assertEqual(resposta.status_code, 302)
        self.u_aluno.refresh_from_db()
        self.assertEqual(self.u_aluno.first_name, "Maria")
        self.assertEqual(self.u_aluno.email, "maria@t.ao")
        self.assertEqual(self.u_aluno.username, "maria@t.ao")

    def test_orientador_mantem_o_username(self):
        self.client.force_login(self.u_ori)
        self.client.post(reverse("contas:editar_perfil"), self.conta(
            self.u_ori, **{"conta-email": "novo@t.ao"}))
        self.u_ori.refresh_from_db()
        self.assertEqual(self.u_ori.email, "novo@t.ao")
        self.assertEqual(self.u_ori.username, "joao.ori")

    def test_email_repetido_e_rejeitado(self):
        self.client.force_login(self.u_aluno)
        resposta = self.client.post(reverse("contas:editar_perfil"), self.conta(
            self.u_aluno, **{"conta-email": "emp@t.ao"}))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Já existe uma conta com este email.")
        self.u_aluno.refresh_from_db()
        self.assertEqual(self.u_aluno.email, "aluno@t.ao")

    def test_accao_invalida(self):
        self.client.force_login(self.u_aluno)
        resposta = self.client.post(reverse("contas:editar_perfil"), {"accao": "xpto"})
        self.assertRedirects(resposta, reverse("contas:editar_perfil"), fetch_redirect_response=False)


class SenhaTests(PerfilBase):
    def test_altera_senha_e_mantem_sessao(self):
        self.client.force_login(self.u_aluno)
        nova = "Outra-Senha-9876"
        resposta = self.client.post(reverse("contas:editar_perfil"), {
            "accao": "senha", "senha-old_password": SENHA,
            "senha-new_password1": nova, "senha-new_password2": nova,
        })
        self.assertEqual(resposta.status_code, 302)
        self.u_aluno.refresh_from_db()
        self.assertTrue(self.u_aluno.check_password(nova))
        self.assertEqual(self.client.get(reverse("estudantes:painel")).status_code, 200)

    def test_senha_actual_errada(self):
        self.client.force_login(self.u_aluno)
        nova = "Outra-Senha-9876"
        resposta = self.client.post(reverse("contas:editar_perfil"), {
            "accao": "senha", "senha-old_password": "errada",
            "senha-new_password1": nova, "senha-new_password2": nova,
        })
        self.assertEqual(resposta.status_code, 200)
        self.u_aluno.refresh_from_db()
        self.assertTrue(self.u_aluno.check_password(SENHA))


class PerfilEspecificoTests(PerfilBase):
    def test_estudante_edita_resumo(self):
        self.client.force_login(self.u_aluno)
        self.client.post(reverse("contas:editar_perfil"), {"accao": "perfil", "perfil-resumo": "Gosto de Django"})
        self.aluno.refresh_from_db()
        self.assertEqual(self.aluno.resumo, "Gosto de Django")

    def test_empresa_edita_dados_mas_nao_o_nif(self):
        self.client.force_login(self.u_emp)
        self.client.post(reverse("contas:editar_perfil"), {
            "accao": "perfil", "perfil-nome": "Emp Nova", "perfil-sector": "TI",
            "perfil-telefone": "923", "perfil-endereco": "Luanda", "perfil-nif": "999",
        })
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.nome, "Emp Nova")
        self.assertEqual(self.empresa.sector, "TI")
        self.assertEqual(self.empresa.nif, "1000000001")

    def test_orientador_edita_cargo(self):
        self.client.force_login(self.u_ori)
        self.client.post(reverse("contas:editar_perfil"), {"accao": "perfil", "perfil-cargo": "Director"})
        self.orientador.refresh_from_db()
        self.assertEqual(self.orientador.cargo, "Director")


class DocumentosTests(PerfilBase):
    def _limpar(self):
        for d in self.aluno.documentos.all():
            d.ficheiro.delete(save=False)

    def _enviar(self):
        return self.client.post(reverse("contas:editar_perfil"), {
            "accao": "documentos",
            "documentos-declaracao_notas": SimpleUploadedFile("n.pdf", b"%PDF-1.4 a"),
            "documentos-declaracao_frequencia": SimpleUploadedFile("f.pdf", b"%PDF-1.4 b"),
        })

    def test_aprovado_nao_pode_alterar_documentos(self):
        self.aluno.registo_estado = PerfilEstudante.Registo.APROVADO
        self.aluno.save()
        self.client.force_login(self.u_aluno)
        self._enviar()
        self.assertEqual(self.aluno.documentos.count(), 0)

    def test_pendente_envia_documentos(self):
        self.aluno.registo_estado = PerfilEstudante.Registo.PENDENTE
        self.aluno.save()
        self.client.force_login(self.u_aluno)
        self._enviar()
        self.assertEqual(self.aluno.documentos.count(), 2)
        self._limpar()

    def test_devolvido_volta_a_pendente(self):
        self.aluno.registo_estado = PerfilEstudante.Registo.DEVOLVIDO
        self.aluno.save()
        self.client.force_login(self.u_aluno)
        self._enviar()
        self.aluno.refresh_from_db()
        self.assertEqual(self.aluno.registo_estado, PerfilEstudante.Registo.PENDENTE)
        self._limpar()
