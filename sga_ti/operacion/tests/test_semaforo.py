from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from operacion import servicios
from operacion.tests.utilidades import preparar_catalogo


class SemaforoPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.datos = preparar_catalogo()
        cls.meta = cls.datos["meta_energia"]

    def test_valor_en_el_umbral_es_normal(self):
        self.assertEqual(servicios.clasificar_estado(Decimal("7650.00"), self.meta), "NORMAL")

    def test_valor_bajo_el_umbral_es_normal(self):
        self.assertEqual(servicios.clasificar_estado(Decimal("7000.00"), self.meta), "NORMAL")

    def test_valor_sobre_el_umbral_es_advertencia(self):
        self.assertEqual(servicios.clasificar_estado(Decimal("7650.01"), self.meta), "ADVERTENCIA")

    def test_valor_igual_a_la_meta_es_advertencia(self):
        self.assertEqual(servicios.clasificar_estado(Decimal("8500.00"), self.meta), "ADVERTENCIA")

    def test_valor_sobre_la_meta_es_alerta(self):
        self.assertEqual(servicios.clasificar_estado(Decimal("8500.01"), self.meta), "ALERTA")

    def test_umbral_de_la_meta_es_el_porcentaje_aplicado(self):
        self.assertEqual(self.meta.valor_activacion, Decimal("7650.00"))

    def test_desvio_negativo_cuando_no_alcanza_la_meta(self):
        self.assertEqual(
            servicios.calcular_desvio(Decimal("8100.00"), Decimal("8500.00")), Decimal("-4.71")
        )

    def test_desvio_cero_en_la_meta(self):
        self.assertEqual(
            servicios.calcular_desvio(Decimal("8500.00"), Decimal("8500.00")), Decimal("0.00")
        )

    def test_desvio_positivo_sobre_la_meta(self):
        self.assertEqual(
            servicios.calcular_desvio(Decimal("8900.00"), Decimal("8500.00")), Decimal("4.71")
        )

    def test_desvio_rechaza_meta_no_positiva(self):
        with self.assertRaises(ValidationError):
            servicios.calcular_desvio(Decimal("10.00"), Decimal("0.00"))
