import secrets

from django.test import Client, TestCase
from django.urls import reverse

from ambiental.models import AspectoAmbiental, Indicador, MetaAmbiental, Proceso
from ambiental import servicios
from cuentas.models import Usuario
from cuentas.servicios import crear_usuario

DATOS_PROCESO = {"codigo": "PR-09", "nombre": "Proceso", "responsable": "Responsable"}
DATOS_INDICADOR = {
    "codigo": "IND-09",
    "nombre": "Indicador",
    "unidad_medida": "kWh",
    "periodicidad": "Mensual",
}


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


class PermisosParametrizacionPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        crear_usuario(username="keiner", password=cls.clave, rol=Usuario.Rol.OPERADOR)
        crear_usuario(username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA)
        proceso = servicios.crear_proceso(codigo="PR-01", nombre="Proceso", responsable="Responsable")
        cls.aspecto = AspectoAmbiental.objects.create(
            proceso=proceso,
            codigo="ASP-01",
            nombre="Aspecto",
            impacto_asociado="Impacto",
            es_significativo=True,
            criterio_significancia="Criterio",
        )
        cls.indicador = Indicador.objects.create(
            aspecto=cls.aspecto, codigo="IND-01", nombre="Indicador", unidad_medida="kWh", periodicidad="Mensual"
        )

    def setUp(self):
        self.anonimo = Client()
        self.operador = Client()
        self.operador.login(username="keiner", password=self.clave)
        self.responsable = Client()
        self.responsable.login(username="fcastro", password=self.clave)

    def test_anonimo_redirige_a_entrada(self):
        for nombre in ("parametrizacion", "indicador_nuevo", "meta_nueva"):
            respuesta = self.anonimo.get(reverse("ambiental:%s" % nombre))
            self.assertEqual(respuesta.status_code, 302, nombre)
            self.assertIn(reverse("cuentas:entrada"), respuesta.url, nombre)

    def test_operador_denegado_en_get(self):
        for nombre in ("parametrizacion", "indicador_nuevo", "meta_nueva"):
            self.assertEqual(self.operador.get(reverse("ambiental:%s" % nombre)).status_code, 403, nombre)

    def test_operador_denegado_en_post_directo(self):
        datos = DATOS_INDICADOR | {"aspecto": str(self.aspecto.pk)}
        respuesta = self.operador.post(reverse("ambiental:indicador_nuevo"), datos)
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Indicador.objects.filter(codigo="IND-09").exists())

    def test_responsable_accede_a_parametrizacion(self):
        self.assertEqual(self.responsable.get(reverse("ambiental:parametrizacion")).status_code, 200)

    def test_responsable_puede_crear_indicador_por_post_directo(self):
        datos = DATOS_INDICADOR | {"aspecto": str(self.aspecto.pk)}
        respuesta = self.responsable.post(reverse("ambiental:indicador_nuevo"), datos)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Indicador.objects.filter(codigo="IND-09").exists())

    def test_responsable_puede_crear_meta_por_post_directo(self):
        respuesta = self.responsable.post(
            reverse("ambiental:meta_nueva"),
            {
                "indicador": str(self.indicador.pk),
                "anio_vigencia": "2026",
                "valor_limite": "100",
                "umbral_advertencia_pct": "90",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(MetaAmbiental.objects.filter(indicador=self.indicador, anio_vigencia=2026).exists())

    def test_post_sin_csrf_rechazado(self):
        estricto = Client(enforce_csrf_checks=True)
        estricto.login(username="fcastro", password=self.clave)
        respuesta = estricto.post(
            reverse("ambiental:meta_nueva"),
            {
                "indicador": str(self.indicador.pk),
                "anio_vigencia": "2026",
                "valor_limite": "100",
                "umbral_advertencia_pct": "90",
            },
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(MetaAmbiental.objects.exists())

    def test_navegacion_oculta_para_operador(self):
        respuesta = self.operador.get(reverse("core:inicio"))
        self.assertNotContains(respuesta, "Parámetros e indicadores")

    def test_navegacion_muestra_para_responsable(self):
        respuesta = self.responsable.get(reverse("core:inicio"))
        self.assertContains(respuesta, "Parámetros e indicadores")
