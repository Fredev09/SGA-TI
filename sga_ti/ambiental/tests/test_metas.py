from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from ambiental.models import AspectoAmbiental, Indicador, MetaAmbiental, Proceso
from ambiental import servicios


def preparar_indicador(codigo="IND-01"):
    proceso = Proceso.objects.create(codigo="PR-01", nombre="Proceso", responsable="Responsable")
    aspecto = AspectoAmbiental.objects.create(
        proceso=proceso,
        codigo="ASP-01",
        nombre="Aspecto",
        impacto_asociado="Impacto",
        es_significativo=True,
        criterio_significancia="Criterio",
    )
    return Indicador.objects.create(
        aspecto=aspecto, codigo=codigo, nombre="Indicador", unidad_medida="kWh", periodicidad="Mensual"
    )


def datos_meta(**campos):
    datos = {
        "anio_vigencia": 2026,
        "valor_limite": Decimal("8500.00"),
        "operador": "<=",
        "umbral_advertencia_pct": 90,
    }
    datos.update(campos)
    return datos


class ModeloMetaPruebas(TestCase):
    def setUp(self):
        self.indicador = preparar_indicador()

    def test_meta_valida_se_guarda(self):
        meta = MetaAmbiental.objects.create(indicador=self.indicador, **datos_meta())
        self.assertEqual(meta.operador, "<=")
        self.assertEqual(meta.valor_limite, Decimal("8500.00"))
        self.assertEqual(meta.umbral_advertencia_pct, 90)
        self.assertEqual(meta.anio_vigencia, 2026)

    def test_hereda_versionado(self):
        meta = MetaAmbiental.objects.create(indicador=self.indicador, **datos_meta())
        self.assertEqual(meta.version, 1)
        self.assertIsNotNone(meta.fecha_creacion)
        self.assertIsNotNone(meta.fecha_actualizacion)

    def test_valor_limite_no_positivo_rechazado_en_bd(self):
        for valor in (Decimal("0.00"), Decimal("-5.00")):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    MetaAmbiental.objects.create(
                        indicador=self.indicador, **datos_meta(valor_limite=valor)
                    )

    def test_umbral_fuera_de_rango_rechazado_en_bd(self):
        for umbral in (49, 100):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    MetaAmbiental.objects.create(
                        indicador=self.indicador, **datos_meta(umbral_advertencia_pct=umbral)
                    )

    def test_operador_distinto_de_mayor_igual_rechazado_en_bd(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MetaAmbiental.objects.create(indicador=self.indicador, **datos_meta(operador=">="))

    def test_unicidad_indicador_anio_rechazada_en_bd(self):
        MetaAmbiental.objects.create(indicador=self.indicador, **datos_meta())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MetaAmbiental.objects.create(indicador=self.indicador, **datos_meta())

    def test_borrar_indicador_con_metas_esta_protegido(self):
        MetaAmbiental.objects.create(indicador=self.indicador, **datos_meta())
        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.indicador.delete()

    def test_valor_activacion_calculado(self):
        meta = MetaAmbiental.objects.create(indicador=self.indicador, **datos_meta())
        self.assertEqual(meta.valor_activacion, Decimal("7650.00"))

    def test_valor_activacion_redondea_a_dos_decimales(self):
        meta = MetaAmbiental.objects.create(
            indicador=self.indicador,
            **datos_meta(valor_limite=Decimal("333.33"), umbral_advertencia_pct=90),
        )
        self.assertEqual(meta.valor_activacion, Decimal("300.00"))

    def test_valor_activacion_con_umbral_noventa_y_nueve(self):
        meta = MetaAmbiental.objects.create(
            indicador=self.indicador,
            **datos_meta(valor_limite=Decimal("100.00"), umbral_advertencia_pct=99),
        )
        self.assertEqual(meta.valor_activacion, Decimal("99.00"))


class CrearMetaPruebas(TestCase):
    def setUp(self):
        self.indicador = preparar_indicador()

    def test_crear_meta_valida_fuerza_mayor_igual(self):
        meta = servicios.crear_meta(
            indicador=self.indicador,
            anio_vigencia=2026,
            valor_limite=Decimal("8500"),
            umbral_advertencia_pct=90,
        )
        self.assertEqual(meta.operador, "<=")
        self.assertEqual(meta.anio_vigencia, 2026)
        self.assertEqual(meta.valor_limite, Decimal("8500"))

    def test_valor_limite_no_positivo_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_meta(
                indicador=self.indicador,
                anio_vigencia=2026,
                valor_limite=Decimal("0"),
                umbral_advertencia_pct=90,
            )
        self.assertIn("El límite mensual debe ser numéricamente positivo.", contexto.exception.messages)

    def test_valor_limite_no_numerico_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_meta(
                indicador=self.indicador,
                anio_vigencia=2026,
                valor_limite="no-numero",
                umbral_advertencia_pct=90,
            )
        self.assertIn("El límite mensual debe ser un número.", contexto.exception.messages)

    def test_umbral_fuera_de_rango_rechazado(self):
        for umbral in (49, 100):
            with self.assertRaises(ValidationError) as contexto:
                servicios.crear_meta(
                    indicador=self.indicador,
                    anio_vigencia=2026,
                    valor_limite=Decimal("8500"),
                    umbral_advertencia_pct=umbral,
                )
            self.assertIn(
                "El umbral de advertencia debe estar entre 50% y 99%.", contexto.exception.messages
            )

    def test_operador_no_mayor_igual_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_meta(
                indicador=self.indicador,
                anio_vigencia=2026,
                valor_limite=Decimal("8500"),
                umbral_advertencia_pct=90,
                operador=">=",
            )
        self.assertIn(
            "Solo se admiten metas de tipo máximo permitido (<=).", contexto.exception.messages
        )

    def test_unicidad_indicador_anio_rechazada(self):
        servicios.crear_meta(
            indicador=self.indicador,
            anio_vigencia=2026,
            valor_limite=Decimal("8500"),
            umbral_advertencia_pct=90,
        )
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_meta(
                indicador=self.indicador,
                anio_vigencia=2026,
                valor_limite=Decimal("100"),
                umbral_advertencia_pct=90,
            )
        self.assertIn(
            "El indicador IND-01 ya tiene una meta para el año 2026.", contexto.exception.messages
        )

    def test_indicador_invalido_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_meta(
                indicador="no-es-indicador",
                anio_vigencia=2026,
                valor_limite=Decimal("8500"),
                umbral_advertencia_pct=90,
            )
        self.assertIn("El indicador indicado no existe.", contexto.exception.messages)

    def test_anio_no_numerico_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_meta(
                indicador=self.indicador,
                anio_vigencia="abc",
                valor_limite=Decimal("8500"),
                umbral_advertencia_pct=90,
            )
        self.assertIn("Ingrese el año de vigencia de la meta.", contexto.exception.messages)

    def test_anio_distinto_no_es_duplicado(self):
        servicios.crear_meta(
            indicador=self.indicador,
            anio_vigencia=2026,
            valor_limite=Decimal("8500"),
            umbral_advertencia_pct=90,
        )
        servicios.crear_meta(
            indicador=self.indicador,
            anio_vigencia=2027,
            valor_limite=Decimal("8600"),
            umbral_advertencia_pct=90,
        )
        self.assertEqual(MetaAmbiental.objects.count(), 2)

    def test_rechazo_no_deja_meta_sin_guardar(self):
        with self.assertRaises(ValidationError):
            servicios.crear_meta(
                indicador=self.indicador,
                anio_vigencia=2026,
                valor_limite=Decimal("-1"),
                umbral_advertencia_pct=90,
            )
        self.assertFalse(MetaAmbiental.objects.exists())
