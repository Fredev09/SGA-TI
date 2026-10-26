from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ambiental.models import MetaAmbiental
from gestion.models import NoConformidad
from operacion import servicios
from operacion.models import Medicion
from operacion.tests.utilidades import ANIO, crear_usuarios, preparar_catalogo


class DashboardPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()
        cls.cliente = Client()
        cls.cliente.login(username="keiner", password=cls.clave)

    def test_dashboard_vacio_muestra_el_estado_inicial(self):
        respuesta = self.cliente.get(reverse("core:inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Sin mediciones registradas para este periodo")
        self.assertEqual(respuesta.context["resumen_nc"]["irnc"], Decimal("0.00"))
        self.assertIsNone(respuesta.context["tendencia"])

    def test_dashboard_muestra_las_mediciones_y_los_estados(self):
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8100.00",
            evidencia="Factura EE-2026-09",
        )
        respuesta = self.cliente.get(reverse("core:inicio"))
        self.assertContains(respuesta, "IND-ENE-01")
        self.assertContains(respuesta, "8100,00")
        self.assertContains(respuesta, "8500,00")
        self.assertContains(respuesta, "Advertencia")
        self.assertEqual(respuesta.context["conteo"]["ADVERTENCIA"], 1)

    def test_dashboard_filtra_por_mes(self):
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=8,
            valor_medido="7000.00",
            evidencia="Factura EE-2026-08",
        )
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8900.00",
            evidencia="Factura EE-2026-09",
        )
        respuesta = self.cliente.get(reverse("core:inicio"), {"mes": "8"})
        self.assertEqual(len(respuesta.context["mediciones"]), 1)
        self.assertContains(respuesta, "7000,00")
        self.assertContains(respuesta, "Agosto 2026")
        self.assertNotContains(respuesta, "Septiembre 2026")
        self.assertEqual(respuesta.context["conteo"]["NORMAL"], 1)
        self.assertEqual(respuesta.context["conteo"]["ALERTA"], 0)

    def test_dashboard_filtra_por_anio(self):
        MetaAmbiental.objects.create(
            indicador=self.datos["energia"],
            anio_vigencia=ANIO - 1,
            valor_limite=Decimal("8500.00"),
            operador="<=",
            umbral_advertencia_pct=90,
        )
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
            indicador=self.datos["energia"],
            anio=ANIO - 1,
            mes=9,
            valor_medido="7900.00",
            evidencia="Factura EE-2025-09",
        )
        respuesta = self.cliente.get(reverse("core:inicio"), {"anio": ANIO - 1})
        self.assertEqual(len(respuesta.context["mediciones"]), 1)
        self.assertEqual(respuesta.context["anio"], ANIO - 1)

    def test_dashboard_calcula_el_irnc(self):
        NoConformidad.objects.create(
            medicion=None,
            origen="MANUAL",
            codigo="NC-%s-01" % ANIO,
            fecha_deteccion=timezone.now(),
            descripcion="Hallazgo de auditoría interna",
            severidad="Media",
            estado="CERRADA",
        )
        NoConformidad.objects.create(
            medicion=None,
            origen="AUDITORIA",
            codigo="NC-%s-02" % ANIO,
            fecha_deteccion=timezone.now(),
            descripcion="Hallazgo pendiente de tratamiento",
            severidad="Alta",
            estado="ABIERTA",
        )
        respuesta = self.cliente.get(reverse("core:inicio"))
        self.assertEqual(respuesta.context["resumen_nc"]["irnc"], Decimal("50.00"))
        self.assertEqual(respuesta.context["resumen_nc"]["total"], 2)
        self.assertEqual(respuesta.context["resumen_nc"]["activas"], 1)
        self.assertContains(respuesta, "50,00")

    def test_dashboard_incluye_la_tendencia_y_el_panel_de_no_conformidades(self):
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8900.00",
            evidencia="Factura EE-2026-09",
        )
        respuesta = self.cliente.get(reverse("core:inicio"))
        tendencia = respuesta.context["tendencia"]
        self.assertEqual(len(tendencia["puntos"]), 1)
        self.assertTrue(tendencia["polilinea"])
        self.assertIsNotNone(tendencia["meta_y"])
        self.assertEqual(tendencia["meta"], Decimal("8500.00"))
        self.assertEqual(tendencia["umbral"], Decimal("7650.00"))
        self.assertContains(respuesta, "No conformidades activas")
        self.assertContains(respuesta, "NC-%s-01" % ANIO)
        self.assertContains(respuesta, "Severidad Alta")

    def test_dashboard_sin_no_conformidades_muestra_estado_vacio(self):
        respuesta = self.cliente.get(reverse("core:inicio"))
        self.assertContains(respuesta, "Sin no conformidades activas en el periodo")

    def test_anonimo_es_redirigido_a_la_entrada(self):
        cliente = Client()
        respuesta = cliente.get(reverse("core:inicio"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("cuentas:entrada"), respuesta.url)

    def test_responsable_tambien_puede_ver_el_dashboard(self):
        cliente = Client()
        cliente.login(username="fcastro", password=self.clave)
        self.assertEqual(cliente.get(reverse("core:inicio")).status_code, 200)

    def test_el_indicador_seleccionado_se_puede_cambiar(self):
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
        respuesta = self.cliente.get(
            reverse("core:inicio"), {"indicador": self.datos["agua"].pk}
        )
        self.assertEqual(respuesta.context["indicador_seleccionado"], self.datos["agua"])
        self.assertEqual(len(respuesta.context["tendencia"]["puntos"]), 1)
        self.assertEqual(Medicion.objects.count(), 2)
