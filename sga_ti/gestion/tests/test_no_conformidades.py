from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from gestion import servicios
from gestion.models import NoConformidad
from operacion import servicios as operacion_servicios
from operacion.tests.utilidades import ANIO, crear_usuarios, preparar_catalogo


def crear_no_conformidad(**extras):
    datos = {
        "medicion": None,
        "origen": "MANUAL",
        "codigo": "NC-%s-01" % ANIO,
        "fecha_deteccion": timezone.now(),
        "descripcion": "Hallazgo registrado manualmente",
        "severidad": "Media",
        "estado": "ABIERTA",
    }
    datos.update(extras)
    return NoConformidad.objects.create(**datos)


class NoConformidadPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()

    def test_resumen_vacio_da_irnc_cero(self):
        resumen = servicios.resumen_no_conformidades(ANIO)
        self.assertEqual(resumen["total"], 0)
        self.assertEqual(resumen["irnc"], Decimal("0.00"))
        self.assertEqual(resumen["activas"], 0)

    def test_resumen_calcula_el_irnc(self):
        crear_no_conformidad(estado="CERRADA")
        crear_no_conformidad(codigo="NC-%s-02" % ANIO, origen="AUDITORIA")
        resumen = servicios.resumen_no_conformidades(ANIO)
        self.assertEqual(resumen["total"], 2)
        self.assertEqual(resumen["cerradas"], 1)
        self.assertEqual(resumen["activas"], 1)
        self.assertEqual(resumen["irnc"], Decimal("50.00"))

    def test_resumen_no_mezcla_anios(self):
        crear_no_conformidad(fecha_deteccion=timezone.now() - timedelta(days=400))
        resumen = servicios.resumen_no_conformidades(ANIO)
        self.assertEqual(resumen["total"], 0)

    def test_activas_excluye_las_cerradas(self):
        crear_no_conformidad(estado="CERRADA")
        abierta = crear_no_conformidad(codigo="NC-%s-02" % ANIO)
        activas = list(servicios.no_conformidades_activas(ANIO))
        self.assertEqual([nc.pk for nc in activas], [abierta.pk])

    def test_origen_automatica_exige_medicion(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                crear_no_conformidad(origen="AUTOMATICA")
        self.assertEqual(NoConformidad.objects.count(), 0)

    def test_origen_invalido_es_rechazado(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                crear_no_conformidad(origen="SISTEMA")
        self.assertEqual(NoConformidad.objects.count(), 0)

    def test_estado_invalido_es_rechazado(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                crear_no_conformidad(estado="BLOQUEADA")
        self.assertEqual(NoConformidad.objects.count(), 0)

    def test_codigo_unico(self):
        crear_no_conformidad()
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                crear_no_conformidad(origen="AUDITORIA")
        self.assertEqual(NoConformidad.objects.count(), 1)

    def test_el_codigo_siguiente_no_repite(self):
        crear_no_conformidad()
        self.assertEqual(servicios.codigo_siguiente(ANIO), "NC-%s-02" % ANIO)

    def test_marcar_revision_no_borra_la_no_conformidad(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8900.00",
            evidencia="Factura EE-2026-09",
        )
        no_conformidad = NoConformidad.objects.get(medicion=medicion)
        resultado = servicios.marcar_revision(medicion)
        self.assertEqual(resultado.pk, no_conformidad.pk)
        no_conformidad.refresh_from_db()
        self.assertTrue(no_conformidad.requiere_revision)
        self.assertEqual(no_conformidad.estado, "ABIERTA")
        self.assertEqual(NoConformidad.objects.count(), 1)

    def test_aplicar_reglas_no_toca_lo_normal(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["agua"],
            anio=ANIO,
            mes=9,
            valor_medido="310.00",
            evidencia="Recibo de acueducto 09",
        )
        self.assertIsNone(servicios.aplicar_reglas_de_semaforo(medicion, estado_anterior="NORMAL"))
        self.assertEqual(NoConformidad.objects.count(), 0)
