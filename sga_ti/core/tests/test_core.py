import secrets

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from cuentas.models import Usuario
from cuentas.servicios import crear_usuario


class PlantillaBasePruebas(TestCase):
    def setUp(self):
        self.clave = secrets.token_urlsafe(16)
        crear_usuario(username="base-ope", password=self.clave, rol=Usuario.Rol.OPERADOR)

    def test_entrada_renderiza_identidad_del_prototipo(self):
        respuesta = Client().get(reverse("cuentas:entrada"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "SGA-TI")
        self.assertContains(respuesta, "CloudTech Solutions S.A.S.")
        self.assertContains(respuesta, "ISO 14001:2015")
        self.assertContains(respuesta, "css/base.css")

    def test_inicio_muestra_rol_y_cierre_de_sesion(self):
        self.client.login(username="base-ope", password=self.clave)
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertContains(respuesta, "Operador")
        self.assertContains(respuesta, reverse("cuentas:salida"))
        self.assertContains(respuesta, "Dashboard")
        self.assertContains(respuesta, "Mediciones del periodo")

    def test_inicio_sin_datos_no_simula_contenido(self):
        self.client.login(username="base-ope", password=self.clave)
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertContains(respuesta, "Sin mediciones registradas para este periodo")
        self.assertContains(respuesta, "Sin no conformidades activas en el periodo")
        self.assertNotContains(respuesta, "IND-")
        self.assertNotContains(respuesta, "NC-")

    def test_paginas_autenticadas_no_se_cachean(self):
        self.client.login(username="base-ope", password=self.clave)
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertEqual(respuesta.headers.get("Cache-Control"), "no-store")


class PaginasDeErrorPruebas(TestCase):
    def setUp(self):
        self.clave = secrets.token_urlsafe(16)
        crear_usuario(username="err-ope", password=self.clave, rol=Usuario.Rol.OPERADOR)

    @override_settings(DEBUG=False)
    def test_404_renderiza_plantilla(self):
        self.client.login(username="err-ope", password=self.clave)
        respuesta = self.client.get("/ruta-que-no-existe/")
        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, "Página no encontrada", status_code=404)

    @override_settings(DEBUG=False, ROOT_URLCONF="cuentas.tests.urls_prueba")
    def test_403_sin_trazas(self):
        self.client.login(username="err-ope", password=self.clave)
        respuesta = self.client.get("/zona-restringida/")
        self.assertEqual(respuesta.status_code, 403)
        contenido = respuesta.content.decode()
        self.assertContains(respuesta, "Acceso denegado", status_code=403)
        self.assertNotIn("Traceback", contenido)
        self.assertNotIn("SECRET_KEY", contenido)


class ConfiguracionPruebas(TestCase):
    def test_zona_horaria_es_bogota(self):
        from django.conf import settings

        self.assertEqual(settings.TIME_ZONE, "America/Bogota")
        self.assertTrue(settings.USE_TZ)

    def test_base_de_datos_fuera_de_one_drive(self):
        from django.conf import settings

        ruta = settings.SQLITE_RUTA
        self.assertTrue(ruta.endswith("sga_ti.db"))
        self.assertNotIn("OneDrive", ruta)
        self.assertNotIn("Proyecto Medioambiental", ruta)

    def test_no_hay_administracion_de_django(self):
        from django.conf import settings

        self.assertNotIn("django.contrib.admin", settings.INSTALLED_APPS)

    def test_configuracion_de_seguridad(self):
        from django.conf import settings

        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.SECURE_REFERRER_POLICY, "same-origin")
        self.assertLessEqual(settings.DATA_UPLOAD_MAX_NUMBER_FILES, 2)

    def test_cabeceras_de_seguridad_en_la_respuesta(self):
        respuesta = Client().get(reverse("cuentas:entrada"))
        politica = respuesta.headers.get("Content-Security-Policy", "")
        self.assertIn("default-src 'self'", politica)
        self.assertIn("frame-ancestors 'none'", politica)
        self.assertNotIn("unsafe-inline", politica)
        self.assertEqual(respuesta.headers.get("Permissions-Policy"), "camera=(), microphone=(), geolocation=()")

    def test_los_datos_de_la_bd_no_estan_en_el_repositorio(self):
        from pathlib import Path

        from django.conf import settings

        ruta_bd = Path(settings.SQLITE_RUTA)
        raiz_repo = Path(settings.BASE_DIR).parent
        self.assertFalse(ruta_bd.is_relative_to(raiz_repo))
