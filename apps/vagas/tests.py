from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.empresas.models import Empresa

from .models import Vaga

User = get_user_model()


class AprovacaoDeVagasTests(TestCase):
    def setUp(self):
        utilizador = User.objects.create_user("emp", "emp@t.ao", "x", tipo="EMPRESA")
        self.empresa = Empresa.objects.create(
            utilizador=utilizador, nome="Emp", nif="1000000001"
        )
        self.vaga = Vaga.objects.create(empresa=self.empresa, titulo="Vaga")

    def test_nao_submete_sem_parceria_aprovada(self):
        with self.assertRaises(ValidationError):
            self.vaga.submeter()
        self.assertEqual(self.vaga.estado, Vaga.Estado.RASCUNHO)

    def test_vaga_so_fica_publica_depois_de_o_instic_aprovar(self):
        self.empresa.validar_nif()
        self.vaga.submeter()
        self.assertEqual(self.vaga.estado, Vaga.Estado.EM_ANALISE)
        self.assertEqual(Vaga.objects.publicas().count(), 0)
        self.vaga.publicar()
        self.assertEqual(Vaga.objects.publicas().count(), 1)

    def test_devolver_exige_motivo(self):
        self.empresa.validar_nif()
        self.vaga.submeter()
        with self.assertRaises(ValidationError):
            self.vaga.devolver("  ")
        self.vaga.devolver("Falta indicar os requisitos.")
        self.vaga.refresh_from_db()
        self.assertEqual(self.vaga.estado, Vaga.Estado.RASCUNHO)
        self.assertEqual(self.vaga.motivo_devolucao, "Falta indicar os requisitos.")