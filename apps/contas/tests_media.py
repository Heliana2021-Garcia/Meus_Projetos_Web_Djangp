from django.test import TestCase

from apps.contas.forms import RegistoEstudanteForm


class MediaGeralNoRegistoTests(TestCase):
    def erros(self, valor):
        form = RegistoEstudanteForm(data={"media_geral": valor})
        form.is_valid()
        return form.errors.get("media_geral")

    def test_recusa_media_negativa(self):
        self.assertTrue(self.erros("-1"))

    def test_recusa_media_acima_de_20(self):
        for valor in ("20.01", "25", "100"):
            self.assertTrue(self.erros(valor), valor)

    def test_aceita_os_limites_e_valores_validos(self):
        for valor in ("0", "14", "14.50", "20"):
            self.assertFalse(self.erros(valor), valor)

    def test_campo_tem_limites_no_navegador(self):
        attrs = RegistoEstudanteForm().fields["media_geral"].widget.attrs
        self.assertEqual(str(attrs.get("min")), "0")
        self.assertEqual(str(attrs.get("max")), "20")