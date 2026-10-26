import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from gestion import reportes, servicios
from gestion.models import NoConformidad
from operacion import servicios as operacion_servicios
from operacion.tests.utilidades import ANIO, crear_usuarios, preparar_catalogo


def crear_cerrada(codigo, origen="AUDITORIA"):
    return NoConformidad.objects.create(
        origen=origen,
        codigo=codigo,
        fecha_deteccion=timezone.now(),
        descripcion="Hallazgo cerrado de prueba",
        severidad="Media",
        estado="CERRADA",
        fecha_cierre=timezone.now(),
    )


class ReportePruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()
        for mes, valor in ((1, "8000.00"), (2, "8300.00"), (3, "9000.00")):
            operacion_servicios.registrar_medicion(
                usuario=cls.responsable,
                indicador=cls.datos["energia"],
                anio=ANIO,
                mes=mes,
                valor_medido=valor,
                evidencia="Factura EE-2026-%02d" % mes,
            )
        crear_cerrada("NC-%s-90" % ANIO)

    def setUp(self):
        self.cliente = Client()
        self.cliente.login(username="fcastro", password=self.clave)

    def test_resumen_cumplimiento_cuenta_valores_dentro_de_la_meta(self):
        resumen = reportes.resumen_mediciones(
            operacion_servicios.mediciones_del_periodo(ANIO, None)
        )
        self.assertEqual(resumen["total"], 3)
        self.assertEqual(resumen["cumplidas"], 2)
        self.assertEqual(resumen["incumplidas"], 1)
        self.assertEqual(resumen["cumplimiento"], Decimal("66.67"))

    def test_resumen_sin_mediciones_da_cero(self):
        resumen = reportes.resumen_mediciones(
            operacion_servicios.mediciones_del_periodo(ANIO - 5, None)
        )
        self.assertEqual(resumen["total"], 0)
        self.assertEqual(resumen["cumplimiento"], Decimal("0.00"))

    def test_balance_por_origen(self):
        balance = {fila["origen"]: fila for fila in reportes.balance_no_conformidades(ANIO)}
        self.assertEqual(balance["Automática"]["abiertas"], 1)
        self.assertEqual(balance["Automática"]["cerradas"], 0)
        self.assertEqual(balance["Auditoría"]["cerradas"], 1)
        self.assertEqual(balance["Manual"]["total"], 0)

    def test_vista_reportes_solo_para_responsable(self):
        self.assertEqual(self.cliente.get(reverse("gestion:reportes")).status_code, 200)
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        self.assertEqual(operador.get(reverse("gestion:reportes")).status_code, 403)
        self.assertEqual(Client().get(reverse("gestion:reportes")).status_code, 302)

    def test_vista_reportes_muestra_totales(self):
        respuesta = self.cliente.get(reverse("gestion:reportes"))
        self.assertContains(respuesta, "Cumplimiento de metas")
        self.assertContains(respuesta, "66,67")
        self.assertContains(respuesta, "IND-ENE-01")
        self.assertContains(respuesta, "No conformidades por origen")

    def test_csv_formato_espanol_con_bom(self):
        respuesta = self.cliente.get(reverse("gestion:reportes_csv"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("text/csv", respuesta["Content-Type"])
        self.assertIn("attachment", respuesta["Content-Disposition"])
        self.assertTrue(respuesta.content.startswith(b"\xef\xbb\xbf"))
        texto = respuesta.content.decode("utf-8-sig")
        filas = list(csv.reader(io.StringIO(texto), delimiter=";"))
        resumen = {fila[0]: fila[1] for fila in filas if len(fila) > 1}
        self.assertEqual(resumen["Mediciones registradas"], "3")
        self.assertEqual(resumen["Cumplimiento de metas (%)"], "66,67")
        self.assertEqual(resumen["IRNC (%)"], "50,00")
        self.assertTrue(any("IND-ENE-01" in fila for fila in filas))
        self.assertTrue(any("Automática" in fila for fila in filas))

    def test_csv_neutraliza_formulas(self):
        operacion_servicios.editar_medicion(
            medicion=operacion_servicios.mediciones_del_periodo(ANIO, 3).first(),
            usuario=self.responsable,
            valor_medido="9000.00",
            evidencia="=cmd|' /C calc'!A0",
        )
        respuesta = self.cliente.get(reverse("gestion:reportes_csv"))
        texto = respuesta.content.decode("utf-8-sig")
        self.assertIn("'=cmd", texto)
        self.assertNotIn(";=cmd", texto)

    def test_csv_filtra_por_mes(self):
        respuesta = self.cliente.get(
            reverse("gestion:reportes_csv") + "?anio=%s&mes=3" % ANIO
        )
        texto = respuesta.content.decode("utf-8-sig")
        filas = list(csv.reader(io.StringIO(texto), delimiter=";"))
        resumen = {fila[0]: fila[1] for fila in filas if len(fila) > 1}
        self.assertEqual(resumen["Mediciones registradas"], "1")
        self.assertIn("Marzo", texto)

    def test_csv_solo_para_responsable(self):
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        self.assertEqual(operador.get(reverse("gestion:reportes_csv")).status_code, 403)
        self.assertEqual(Client().get(reverse("gestion:reportes_csv")).status_code, 302)

    def test_totales_coinciden_con_el_dashboard(self):
        mediciones = operacion_servicios.mediciones_del_periodo(ANIO, None)
        respuesta = self.cliente.get(reverse("gestion:reportes_csv"))
        texto = respuesta.content.decode("utf-8-sig")
        self.assertIn("Mediciones registradas;%d" % len(mediciones), texto)
        resumen = servicios.resumen_no_conformidades(ANIO)
        self.assertIn("IRNC (%%);%s" % reportes.numero(resumen["irnc"]), texto)
