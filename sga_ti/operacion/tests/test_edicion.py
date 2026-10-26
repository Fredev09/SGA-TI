from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase

from gestion.models import NoConformidad
from operacion import servicios
from operacion.models import AuditoriaMedicion, Medicion
from operacion.tests.utilidades import ANIO, crear_usuarios, preparar_catalogo


class EdicionMedicionPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()
        cls.medicion_alerta = servicios.registrar_medicion(
            usuario=cls.responsable,
            indicador=cls.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8900.00",
            evidencia="Factura EE-2026-09",
        )
        cls.medicion_normal = servicios.registrar_medicion(
            usuario=cls.responsable,
            indicador=cls.datos["agua"],
            anio=ANIO,
            mes=9,
            valor_medido="310.00",
            evidencia="Recibo de acueducto 09",
        )

    def test_editar_registra_la_bitacora(self):
        servicios.editar_medicion(
            medicion=self.medicion_alerta,
            usuario=self.operador,
            valor_medido="8700.00",
            evidencia="Factura EE-2026-09 corregida",
        )
        registro = AuditoriaMedicion.objects.get(medicion=self.medicion_alerta)
        self.assertEqual(registro.valor_anterior, Decimal("8900.00"))
        self.assertEqual(registro.valor_nuevo, Decimal("8700.00"))
        self.assertEqual(registro.usuario, self.operador)
        self.assertIsNotNone(registro.fecha_modificacion)

    def test_editar_recalcula_estado_y_desvio(self):
        medicion = servicios.editar_medicion(
            medicion=self.medicion_alerta,
            usuario=self.operador,
            valor_medido="7000.00",
            evidencia="Factura EE-2026-09 corregida",
        )
        self.assertEqual(medicion.estado_semaforo, "NORMAL")
        self.assertEqual(medicion.desvio_pct, Decimal("-17.65"))

    def test_editar_recalcula_el_valor_de_la_meta(self):
        self.datos["meta_energia"].valor_limite = Decimal("9000.00")
        self.datos["meta_energia"].save()
        medicion = servicios.editar_medicion(
            medicion=self.medicion_alerta,
            usuario=self.operador,
            valor_medido="8600.00",
            evidencia="Factura EE-2026-09 corregida",
        )
        self.assertEqual(medicion.valor_meta, Decimal("9000.00"))
        self.assertEqual(medicion.estado_semaforo, "ADVERTENCIA")
        self.assertEqual(medicion.desvio_pct, Decimal("-4.44"))

    def test_mejora_de_alerta_marca_revision_sin_borrar_la_no_conformidad(self):
        self.assertEqual(NoConformidad.objects.filter(medicion=self.medicion_alerta).count(), 1)
        servicios.editar_medicion(
            medicion=self.medicion_alerta,
            usuario=self.operador,
            valor_medido="8000.00",
            evidencia="Factura EE-2026-09 corregida",
        )
        self.assertEqual(NoConformidad.objects.filter(medicion=self.medicion_alerta).count(), 1)
        no_conformidad = NoConformidad.objects.get(medicion=self.medicion_alerta)
        self.assertTrue(no_conformidad.requiere_revision)
        self.assertEqual(no_conformidad.estado, "ABIERTA")

    def test_empeora_a_alerta_y_crea_no_conformidad(self):
        self.assertEqual(NoConformidad.objects.filter(medicion=self.medicion_normal).count(), 0)
        servicios.editar_medicion(
            medicion=self.medicion_normal,
            usuario=self.operador,
            valor_medido="400.00",
            evidencia="Recibo de acueducto 09",
        )
        no_conformidad = NoConformidad.objects.get(medicion=self.medicion_normal)
        self.assertEqual(no_conformidad.origen, "AUTOMATICA")
        self.assertEqual(no_conformidad.estado, "ABIERTA")

    def test_editar_con_el_mismo_valor_tambien_registra_bitacora(self):
        servicios.editar_medicion(
            medicion=self.medicion_normal,
            usuario=self.operador,
            valor_medido="310.00",
            evidencia="Recibo de acueducto 09",
        )
        self.assertEqual(AuditoriaMedicion.objects.filter(medicion=self.medicion_normal).count(), 1)

    def test_alerta_mantenido_no_duplica_no_conformidad(self):
        servicios.editar_medicion(
            medicion=self.medicion_alerta,
            usuario=self.operador,
            valor_medido="9100.00",
            evidencia="Factura EE-2026-09 corregida",
        )
        self.assertEqual(NoConformidad.objects.filter(medicion=self.medicion_alerta).count(), 1)
        self.medicion_alerta.refresh_from_db()
        self.assertEqual(self.medicion_alerta.estado_semaforo, "ALERTA")

    def test_editar_rechaza_valor_negativo(self):
        with self.assertRaises(ValidationError):
            servicios.editar_medicion(
                medicion=self.medicion_alerta,
                usuario=self.operador,
                valor_medido="-10.00",
                evidencia="Factura EE-2026-09",
            )
        self.assertEqual(AuditoriaMedicion.objects.count(), 0)
        self.medicion_alerta.refresh_from_db()
        self.assertEqual(self.medicion_alerta.valor_medido, Decimal("8900.00"))

    def test_editar_no_cambia_al_autor_original(self):
        servicios.editar_medicion(
            medicion=self.medicion_alerta,
            usuario=self.operador,
            valor_medido="8700.00",
            evidencia="Factura EE-2026-09 corregida",
        )
        self.medicion_alerta.refresh_from_db()
        self.assertEqual(self.medicion_alerta.usuario, self.responsable)

    def test_las_mediciones_con_hallazgos_no_se_borran(self):
        with self.assertRaises(ProtectedError):
            Medicion.objects.filter(pk=self.medicion_alerta.pk).delete()
        self.assertEqual(Medicion.objects.filter(pk=self.medicion_alerta.pk).count(), 1)
