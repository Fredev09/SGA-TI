import secrets

from django.test import Client, TestCase
from django.urls import reverse

from ambiental.models import AspectoAmbiental, Proceso
from ambiental import servicios
from cuentas.models import Usuario
from cuentas.servicios import crear_usuario

DATOS_PROCESO = {"codigo": "PR-09", "nombre": "Proceso", "responsable": "Responsable"}


class PermisosCatalogoPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        cls.operador = crear_usuario(username="keiner", password=cls.clave, rol=Usuario.Rol.OPERADOR)
        cls.responsable = crear_usuario(
            username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA
        )
        cls.proceso = servicios.crear_proceso(codigo="PR-01", nombre="Proceso", responsable="Responsable")

    def setUp(self):
        self.cliente_anonimo = Client()
        self.cliente_operador = Client()
        self.cliente_operador.login(username="keiner", password=self.clave)
        self.cliente_responsable = Client()
        self.cliente_responsable.login(username="fcastro", password=self.clave)

    def test_anonimo_redirige_a_entrada(self):
        for nombre in ("catalogo", "proceso_nuevo", "aspecto_nuevo"):
            respuesta = self.cliente_anonimo.get(reverse("ambiental:%s" % nombre))
            self.assertEqual(respuesta.status_code, 302, nombre)
            self.assertIn(reverse("cuentas:entrada"), respuesta.url, nombre)

    def test_operador_denegado_en_catalogo(self):
        respuesta = self.cliente_operador.get(reverse("ambiental:catalogo"))
        self.assertEqual(respuesta.status_code, 403)

    def test_operador_denegado_en_formularios(self):
        for nombre in ("proceso_nuevo", "aspecto_nuevo"):
            self.assertEqual(
                self.cliente_operador.get(reverse("ambiental:%s" % nombre)).status_code, 403, nombre
            )

    def test_operador_denegado_en_post_directo(self):
        respuesta = self.cliente_operador.post(
            reverse("ambiental:proceso_nuevo"),
            DATOS_PROCESO,
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Proceso.objects.filter(codigo="PR-09").exists())

    def test_responsable_accede_al_catalogo(self):
        self.assertEqual(self.cliente_responsable.get(reverse("ambiental:catalogo")).status_code, 200)

    def test_responsable_puede_crear_por_post_directo(self):
        respuesta = self.cliente_responsable.post(reverse("ambiental:proceso_nuevo"), DATOS_PROCESO)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Proceso.objects.filter(codigo="PR-09").exists())

    def test_post_sin_csrf_rechazado(self):
        cliente_estricto = Client(enforce_csrf_checks=True)
        cliente_estricto.login(username="fcastro", password=self.clave)
        respuesta = cliente_estricto.post(reverse("ambiental:proceso_nuevo"), DATOS_PROCESO)
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Proceso.objects.filter(codigo="PR-09").exists())

    def test_navegacion_oculta_enlace_para_operador(self):
        respuesta = self.cliente_operador.get(reverse("core:inicio"))
        self.assertNotContains(respuesta, "Catálogo ambiental")

    def test_navegacion_muestra_enlace_para_responsable(self):
        respuesta = self.cliente_responsable.get(reverse("core:inicio"))
        self.assertContains(respuesta, "Catálogo ambiental")

    def test_post_directo_aspecto_valido_como_responsable(self):
        respuesta = self.cliente_responsable.post(
            reverse("ambiental:aspecto_nuevo"),
            {
                "proceso": str(self.proceso.pk),
                "codigo": "ASP-09",
                "nombre": "Aspecto",
                "impacto_asociado": "Impacto",
                "es_significativo": "1",
                "criterio_significancia": "Criterio",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(AspectoAmbiental.objects.filter(codigo="ASP-09").exists())
