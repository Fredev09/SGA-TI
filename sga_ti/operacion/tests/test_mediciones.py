from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from gestion.models import NoConformidad
from ambiental.models import Indicador
from operacion import servicios
from operacion.models import Medicion
from operacion.tests.utilidades import ANIO, crear_usuarios, preparar_catalogo


class RegistroMedicionPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()

    def test_registro_guarda_el_snapshot_de_la_meta(self):
        medicion = servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8100.00",
            evidencia="Factura EE-2026-09",
        )
        self.assertEqual(medicion.valor_meta, Decimal("8500.00"))
        self.assertEqual(medicion.desvio_pct, Decimal("-4.71"))
        self.assertEqual(medicion.estado_semaforo, "ADVERTENCIA")
        self.assertEqual(medicion.usuario, self.responsable)
        self.assertEqual(medicion.evidencia, "Factura EE-2026-09")
        self.assertEqual(medicion.fecha_registro, medicion.fecha_creacion)

    def test_no_admite_dos_mediciones_en_el_mismo_periodo(self):
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8100.00",
            evidencia="Factura EE-2026-09",
        )
        with self.assertRaises(ValidationError):
            servicios.registrar_medicion(
                usuario=self.responsable,
                indicador=self.datos["energia"],
                anio=ANIO,
                mes=9,
                valor_medido="7000.00",
                evidencia="Factura EE-2026-09",
            )
        self.assertEqual(Medicion.objects.count(), 1)

    def test_admite_una_medicion_por_indicador_en_el_mismo_mes(self):
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8100.00",
            evidencia="Factura EE-2026-09",
        )
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["agua"],
            anio=ANIO,
            mes=9,
            valor_medido="310.00",
            evidencia="Recibo de acueducto 09",
        )
        self.assertEqual(Medicion.objects.count(), 2)

    def test_rechaza_indicador_sin_meta_vigente(self):
        sin_meta = Indicador.objects.create(
            aspecto=self.datos["aspecto"],
            codigo="IND-RAE-03",
            nombre="Residuos electrónicos",
            unidad_medida="kg",
            periodicidad="Mensual",
        )
        with self.assertRaises(ValidationError):
            servicios.registrar_medicion(
                usuario=self.responsable,
                indicador=sin_meta,
                anio=ANIO,
                mes=9,
                valor_medido="85.00",
                evidencia="Acta de entrega 09",
            )
        self.assertEqual(Medicion.objects.count(), 0)

    def test_rechaza_valor_negativo(self):
        with self.assertRaises(ValidationError):
            servicios.registrar_medicion(
                usuario=self.responsable,
                indicador=self.datos["energia"],
                anio=ANIO,
                mes=9,
                valor_medido="-10.00",
                evidencia="Factura EE-2026-09",
            )
        self.assertEqual(Medicion.objects.count(), 0)

    def test_rechaza_medicion_sin_evidencia(self):
        with self.assertRaises(ValidationError):
            servicios.registrar_medicion(
                usuario=self.responsable,
                indicador=self.datos["energia"],
                anio=ANIO,
                mes=9,
                valor_medido="8100.00",
                evidencia="   ",
            )
        self.assertEqual(Medicion.objects.count(), 0)

    def test_estado_alerta_crea_no_conformidad_automatica(self):
        medicion = servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8900.00",
            evidencia="Factura EE-2026-09",
        )
        self.assertEqual(medicion.estado_semaforo, "ALERTA")
        no_conformidad = NoConformidad.objects.get(medicion=medicion)
        self.assertEqual(no_conformidad.origen, "AUTOMATICA")
        self.assertEqual(no_conformidad.estado, "ABIERTA")
        self.assertEqual(no_conformidad.severidad, "Alta")
        self.assertFalse(no_conformidad.requiere_revision)
        self.assertEqual(no_conformidad.codigo, "NC-%s-01" % ANIO)

    def test_estado_normal_no_crea_no_conformidad(self):
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="7000.00",
            evidencia="Factura EE-2026-09",
        )
        self.assertEqual(NoConformidad.objects.count(), 0)

    def test_el_codigo_de_no_conformidad_avanza(self):
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8900.00",
            evidencia="Factura EE-2026-09",
        )
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["agua"],
            anio=ANIO,
            mes=9,
            valor_medido="400.00",
            evidencia="Recibo de acueducto 09",
        )
        codigos = sorted(NoConformidad.objects.values_list("codigo", flat=True))
        self.assertEqual(codigos, ["NC-%s-01" % ANIO, "NC-%s-02" % ANIO])

    def test_periodo_fuera_de_rango_es_rechazado(self):
        with self.assertRaises(ValidationError):
            servicios.registrar_medicion(
                usuario=self.responsable,
                indicador=self.datos["energia"],
                anio=ANIO,
                mes=13,
                valor_medido="8100.00",
                evidencia="Factura EE-2026-09",
            )
        self.assertEqual(Medicion.objects.count(), 0)
