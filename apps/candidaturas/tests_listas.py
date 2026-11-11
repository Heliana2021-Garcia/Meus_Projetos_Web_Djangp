from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.candidaturas.models import Candidatura
from apps.empresas.models import Empresa, Orientador
from apps.estudantes.models import Curso, PerfilEstudante
from apps.vagas.models import Vaga

User = get_user_model()


class ListasBase(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nome="Engenharia Informatica", sigla="EI")
        self.outro_curso = Curso.objects.create(nome="Redes", sigla="RD")
        self.u_aluno = User.objects.create_user(
            "ana@t.ao", "ana@t.ao", "x", tipo="ESTUDANTE", first_name="Ana", last_name="Silva"
        )
        self.aluno = PerfilEstudante.objects.create(
            utilizador=self.u_aluno, numero_estudante="A1", curso=self.curso,
            ano_frequencia=3, media_geral=Decimal("15"),
        )
        self.u_emp = User.objects.create_user("emp@t.ao", "emp@t.ao", "x", tipo="EMPRESA")
        self.empresa = Empresa.objects.create(utilizador=self.u_emp, nome="Alfa", nif="1000000001")
        self.empresa.validar_nif()
        self.v1 = Vaga.objects.create(empresa=self.empresa, titulo="Redes Cisco")
        self.v2 = Vaga.objects.create(empresa=self.empresa, titulo="Programador Django")
        self.v1.publicar()
        # v2 fica em rascunho


class VagasDaEmpresaTests(ListasBase):
    def test_pesquisa_e_estado(self):
        self.client.force_login(self.u_emp)
        url = reverse("vagas:minhas")
        r = self.client.get(url, {"q": "django"})
        self.assertEqual([v.titulo for v in r.context["vagas"]], ["Programador Django"])
        r = self.client.get(url, {"estado": "ABERTA"})
        self.assertEqual([v.titulo for v in r.context["vagas"]], ["Redes Cisco"])
        r = self.client.get(url, {"estado": "inexistente"})
        self.assertEqual(len(r.context["vagas"]), 2)


class CandidaturasDoEstudanteTests(ListasBase):
    def test_filtra_por_estado_e_pesquisa(self):
        c1 = Candidatura.objects.create(estudante=self.aluno, vaga=self.v1)
        self.v2.publicar()
        c2 = Candidatura.objects.create(estudante=self.aluno, vaga=self.v2)
        c2.mover_para("TESTE")
        self.client.force_login(self.u_aluno)
        url = reverse("candidaturas:minhas")
        r = self.client.get(url, {"estado": "TESTE"})
        self.assertEqual([c.pk for c in r.context["candidaturas"]], [c2.pk])
        r = self.client.get(url, {"q": "cisco"})
        self.assertEqual([c.pk for c in r.context["candidaturas"]], [c1.pk])
        self.assertEqual(self.client.get(url).status_code, 200)


class EstagiosDaEmpresaTests(ListasBase):
    def test_filtro_por_orientador(self):
        u_ori = User.objects.create_user("ori", "ori@t.ao", "x", tipo="ORIENTADOR")
        ori = Orientador.objects.create(utilizador=u_ori, empresa=self.empresa)
        c = Candidatura.objects.create(estudante=self.aluno, vaga=self.v1)
        for e in ("TESTE", "ENTREVISTA", "PROPOSTA", "APROVADO"):
            c.mover_para(e)
        self.client.force_login(self.u_emp)
        url = reverse("candidaturas:estagios")
        self.assertEqual(len(self.client.get(url, {"orientador": "sem"}).context["estagios"]), 1)
        self.assertEqual(len(self.client.get(url, {"orientador": "com"}).context["estagios"]), 0)
        self.assertEqual(len(self.client.get(url, {"q": "silva"}).context["estagios"]), 1)
        self.assertEqual(len(self.client.get(url, {"q": "zzz"}).context["estagios"]), 0)
        c.orientador = ori
        c.save()
        self.assertEqual(len(self.client.get(url, {"orientador": "com"}).context["estagios"]), 1)


class RegistosPendentesTests(ListasBase):
    def test_pesquisa_e_curso(self):
        self.aluno.registo_estado = PerfilEstudante.Registo.PENDENTE
        self.aluno.save()
        coord = User.objects.create_user("co@t.ao", "co@t.ao", "x", tipo="COORDENADOR")
        self.client.force_login(coord)
        url = reverse("relatorios:estudantes_pendentes")
        self.assertEqual(len(self.client.get(url, {"q": "ana"}).context["perfis"]), 1)
        self.assertEqual(len(self.client.get(url, {"q": "zzz"}).context["perfis"]), 0)
        self.assertEqual(len(self.client.get(url, {"curso": self.curso.pk}).context["perfis"]), 1)
        self.assertEqual(len(self.client.get(url, {"curso": self.outro_curso.pk}).context["perfis"]), 0)
        self.assertEqual(len(self.client.get(url, {"curso": "x"}).context["perfis"]), 1)


class PainelResumoETests(ListasBase):
    def test_candidatura_mais_avancada(self):
        self.v2.publicar()
        Candidatura.objects.create(estudante=self.aluno, vaga=self.v1)
        c2 = Candidatura.objects.create(estudante=self.aluno, vaga=self.v2)
        c2.mover_para("TESTE")
        self.client.force_login(self.u_aluno)
        r = self.client.get(reverse("estudantes:painel"))
        self.assertEqual(r.context["candidatura_avancada"].pk, c2.pk)
        self.assertEqual(r.context["total_activas"], 2)
        self.assertContains(r, "Candidatura mais avançada")

    def test_estagio_actual(self):
        c = Candidatura.objects.create(estudante=self.aluno, vaga=self.v1)
        for e in ("TESTE", "ENTREVISTA", "PROPOSTA", "APROVADO"):
            c.mover_para(e)
        self.client.force_login(self.u_aluno)
        r = self.client.get(reverse("estudantes:painel"))
        self.assertEqual(r.context["estagio_actual"].pk, c.pk)
        self.assertContains(r, "O seu estágio")

    def test_sem_nada_nao_mostra_resumo(self):
        self.client.force_login(self.u_aluno)
        self.assertNotContains(self.client.get(reverse("estudantes:painel")), "Candidatura mais avançada")


class DocumentosRedireccionaTests(ListasBase):
    def test_get_vai_para_editar_perfil(self):
        self.client.force_login(self.u_aluno)
        r = self.client.get(reverse("estudantes:documentos"))
        self.assertRedirects(
            r, reverse("contas:editar_perfil") + "#documentos", fetch_redirect_response=False
        )

    def test_devolver_notifica_com_link_novo(self):
        from apps.core.models import Notificacao

        self.aluno.registo_estado = PerfilEstudante.Registo.PENDENTE
        self.aluno.save()
        coord = User.objects.create_user("co@t.ao", "co@t.ao", "x", tipo="COORDENADOR")
        self.client.force_login(coord)
        self.client.post(reverse("relatorios:devolver_estudante", args=[self.aluno.pk]), {"motivo": "Ilegivel"})
        n = Notificacao.objects.filter(destinatario=self.u_aluno).first()
        self.assertTrue(n.url.endswith("#documentos"))
        self.assertIn(reverse("contas:editar_perfil"), n.url)
