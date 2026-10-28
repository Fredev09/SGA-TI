import json
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from operacion import servicios
from operacion.models import Medicion
from operacion.tests.utilidades import ANIO, crear_usuarios, preparar_catalogo


def archivo_json(contenido, nombre="mediciones.json"):
    return SimpleUploadedFile(
        nombre, contenido.encode("utf-8"), content_type="application/json"
    )


class ExportacionPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()
        servicios.registrar_medicion(
            usuario=cls.responsable,
            indicador=cls.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8100.00",
            evidencia="Factura EE-2026-09",
        )

    def setUp(self):
        self.responsable_cliente = Client()
        self.responsable_cliente.login(username="fcastro", password=self.clave)

    def test_descarga_un_archivo_json(self):
        respuesta = self.responsable_cliente.get(
            reverse("operacion:exportar_mediciones")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta["Content-Type"], "application/json; charset=utf-8"
        )
        self.assertIn("attachment", respuesta["Content-Disposition"])

    def test_el_archivo_incluye_las_mediciones(self):
        respuesta = self.responsable_cliente.get(
            reverse("operacion:exportar_mediciones")
        )
        contenido = json.loads(respuesta.content.decode("utf-8"))
        self.assertEqual(contenido["origen"], "SGA-TI")
        self.assertEqual(len(contenido["mediciones"]), 1)
        registro = contenido["mediciones"][0]
        self.assertEqual(registro["indicador"], "IND-ENE-01")
        self.assertEqual(registro["usuario"], "fcastro")
        self.assertEqual(registro["anio"], ANIO)
        self.assertEqual(registro["mes"], 9)
        self.assertEqual(registro["valor"], "8100.00")
        self.assertEqual(registro["evidencia"], "Factura EE-2026-09")

    def test_la_pantalla_muestra_el_total_de_mediciones(self):
        respuesta = self.responsable_cliente.get(reverse("operacion:sincronizacion"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Exportar mediciones")
        self.assertContains(respuesta, "Importar mediciones")
        self.assertEqual(respuesta.context["total_mediciones"], 1)


class ImportacionPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()

    def setUp(self):
        self.responsable_cliente = Client()
        self.responsable_cliente.login(username="fcastro", password=self.clave)

    def _registro(self, **cambios):
        registro = {
            "indicador": "IND-ENE-01",
            "usuario": "fcastro",
            "anio": ANIO,
            "mes": 9,
            "valor": "8100.00",
            "evidencia": "Factura EE-2026-09",
        }
        registro.update(cambios)
        return registro

    def _importar(self, registros):
        contenido = json.dumps({"mediciones": registros})
        return self.responsable_cliente.post(
            reverse("operacion:importar_mediciones"),
            {"archivo": archivo_json(contenido)},
        )

    def test_importa_una_medicion_nueva(self):
        respuesta = self._importar([self._registro()])
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Medicion.objects.count(), 1)
        medicion = Medicion.objects.get()
        self.assertEqual(medicion.valor_medido, Decimal("8100.00"))
        self.assertEqual(medicion.valor_meta, Decimal("8500.00"))
        self.assertEqual(medicion.estado_semaforo, "ADVERTENCIA")
        self.assertEqual(medicion.evidencia, "Factura EE-2026-09")
        self.assertEqual(medicion.usuario.username, "fcastro")
        self.assertEqual(respuesta.context["resultado"]["importadas"], 1)
        self.assertEqual(respuesta.context["total_mediciones"], 1)

    def test_reimportar_el_mismo_archivo_no_duplica(self):
        self._importar([self._registro()])
        respuesta = self._importar([self._registro()])
        self.assertEqual(Medicion.objects.count(), 1)
        self.assertEqual(respuesta.context["resultado"]["importadas"], 0)
        self.assertEqual(respuesta.context["resultado"]["omitidas"], 1)

    def test_un_periodo_ya_registrado_no_se_sobrescribe(self):
        servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8100.00",
            evidencia="Factura EE-2026-09",
        )
        respuesta = self._importar([self._registro(valor="7000.00")])
        self.assertEqual(Medicion.objects.count(), 1)
        self.assertEqual(
            Medicion.objects.get().valor_medido, Decimal("8100.00")
        )
        self.assertEqual(respuesta.context["resultado"]["omitidas"], 1)

    def test_informa_el_indicador_desconocido(self):
        respuesta = self._importar([self._registro(indicador="IND-XXX-99")])
        self.assertEqual(Medicion.objects.count(), 0)
        resultado = respuesta.context["resultado"]
        self.assertEqual(resultado["importadas"], 0)
        self.assertEqual(len(resultado["errores"]), 1)
        self.assertIn("IND-XXX-99", resultado["errores"][0]["detalle"])

    def test_informa_el_usuario_desconocido(self):
        respuesta = self._importar([self._registro(usuario="nadie")])
        self.assertEqual(Medicion.objects.count(), 0)
        self.assertIn("nadie", respuesta.context["resultado"]["errores"][0]["detalle"])

    def test_informa_el_mes_invalido(self):
        respuesta = self._importar([self._registro(mes=13)])
        self.assertEqual(Medicion.objects.count(), 0)
        self.assertEqual(len(respuesta.context["resultado"]["errores"]), 1)

    def test_informa_el_valor_no_numerico(self):
        respuesta = self._importar([self._registro(valor="ocho mil")])
        self.assertEqual(Medicion.objects.count(), 0)
        self.assertEqual(len(respuesta.context["resultado"]["errores"]), 1)

    def test_procesa_las_filas_validas_y_reporta_las_invalidas(self):
        respuesta = self._importar(
            [self._registro(), self._registro(mes=13)]
        )
        self.assertEqual(Medicion.objects.count(), 1)
        resultado = respuesta.context["resultado"]
        self.assertEqual(resultado["importadas"], 1)
        self.assertEqual(len(resultado["errores"]), 1)

    def test_acepta_una_lista_simple(self):
        contenido = json.dumps([self._registro()])
        respuesta = self.responsable_cliente.post(
            reverse("operacion:importar_mediciones"),
            {"archivo": archivo_json(contenido)},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Medicion.objects.count(), 1)

    def test_rechaza_un_archivo_que_no_es_json(self):
        respuesta = self.responsable_cliente.post(
            reverse("operacion:importar_mediciones"),
            {"archivo": archivo_json("esto no es json")},
            follow=True,
        )
        self.assertContains(respuesta, "no es un JSON válido")
        self.assertEqual(Medicion.objects.count(), 0)

    def test_rechaza_un_archivo_sin_lista_de_mediciones(self):
        respuesta = self.responsable_cliente.post(
            reverse("operacion:importar_mediciones"),
            {"archivo": archivo_json(json.dumps({"otra": []}))},
            follow=True,
        )
        self.assertContains(respuesta, "no contiene una lista de mediciones")

    def test_rechaza_un_archivo_superior_a_dos_megas(self):
        contenido = "x" * (2 * 1024 * 1024 + 1)
        respuesta = self.responsable_cliente.post(
            reverse("operacion:importar_mediciones"),
            {"archivo": archivo_json(contenido)},
            follow=True,
        )
        self.assertContains(respuesta, "supera el límite de 2 MB")
        self.assertEqual(Medicion.objects.count(), 0)

    def test_rechaza_una_peticion_sin_archivo(self):
        respuesta = self.responsable_cliente.post(
            reverse("operacion:importar_mediciones"), {}, follow=True
        )
        self.assertContains(respuesta, "Seleccione un archivo JSON")

    def test_la_importacion_solo_admite_post(self):
        respuesta = self.responsable_cliente.get(
            reverse("operacion:importar_mediciones")
        )
        self.assertEqual(respuesta.status_code, 405)


class PermisosSincronizacionPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        preparar_catalogo()

    def setUp(self):
        self.anonimo = Client()
        self.operador_cliente = Client()
        self.operador_cliente.login(username="keiner", password=self.clave)
        self.responsable_cliente = Client()
        self.responsable_cliente.login(username="fcastro", password=self.clave)

    def test_anonimo_es_redirigido_a_la_entrada(self):
        respuesta = self.anonimo.get(reverse("operacion:sincronizacion"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("cuentas:entrada"), respuesta.url)

    def test_el_operador_no_accede_a_la_pantalla_ni_a_la_descarga(self):
        urls = [
            reverse("operacion:sincronizacion"),
            reverse("operacion:exportar_mediciones"),
        ]
        for url in urls:
            self.assertEqual(
                self.operador_cliente.get(url).status_code, 403, url
            )

    def test_el_operador_no_puede_importar(self):
        contenido = json.dumps(
            [
                {
                    "indicador": "IND-ENE-01",
                    "usuario": "keiner",
                    "anio": ANIO,
                    "mes": 9,
                    "valor": "8100.00",
                    "evidencia": "Factura EE-2026-09",
                }
            ]
        )
        respuesta = self.operador_cliente.post(
            reverse("operacion:importar_mediciones"),
            {"archivo": archivo_json(contenido)},
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Medicion.objects.count(), 0)

    def test_el_responsable_accede_a_la_pantalla(self):
        respuesta = self.responsable_cliente.get(reverse("operacion:sincronizacion"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Sincronización de mediciones")

    def test_el_operador_no_ve_el_enlace_en_el_menu(self):
        respuesta = self.operador_cliente.get(reverse("core:inicio"))
        self.assertNotContains(respuesta, reverse("operacion:sincronizacion"))

    def test_el_responsable_ve_el_enlace_en_el_menu(self):
        respuesta = self.responsable_cliente.get(reverse("core:inicio"))
        self.assertContains(respuesta, reverse("operacion:sincronizacion"))
