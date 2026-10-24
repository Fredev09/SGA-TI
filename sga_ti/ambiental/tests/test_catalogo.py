import secrets

from django.test import Client, TestCase
from django.urls import reverse

from ambiental.models import AspectoAmbiental, Indicador, Proceso
from ambiental import servicios
from cuentas.models import Usuario
from cuentas.servicios import crear_usuario


class CatalogoPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        cls.responsable = crear_usuario(
            username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA
        )
        cls.proceso = servicios.crear_proceso(
            codigo="PR-01", nombre="Operación de infraestructura TI", responsable="Carlos Martínez"
        )
        cls.aspecto_significativo = AspectoAmbiental.objects.create(
            proceso=cls.proceso,
            codigo="ASP-01",
            nombre="Consumo de energía eléctrica",
            impacto_asociado="Agotamiento de recursos no renovables",
            es_significativo=True,
            criterio_significancia="Uso de recursos no renovables por encima del umbral interno",
        )
        cls.aspecto_no_significativo = AspectoAmbiental.objects.create(
            proceso=cls.proceso,
            codigo="ASP-02",
            nombre="Consumo de agua potable",
            impacto_asociado="Presión sobre el recurso hídrico local",
            es_significativo=False,
            criterio_significancia="Consumo mensual dentro del rango esperado",
        )
        cls.indicador = Indicador.objects.create(
            aspecto=cls.aspecto_significativo,
            codigo="IND-ENE-01",
            nombre="Consumo mensual de energía eléctrica",
            unidad_medida="kWh",
            periodicidad="Mensual",
        )
        cls.cliente = Client()
        cls.cliente.login(username="fcastro", password=cls.clave)

    def test_catalogo_muestra_procesos_y_aspectos(self):
        respuesta = self.cliente.get(reverse("ambiental:catalogo"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "PR-01")
        self.assertContains(respuesta, "Operación de infraestructura TI")
        self.assertContains(respuesta, "ASP-01")
        self.assertContains(respuesta, "Consumo de energía eléctrica")
        self.assertContains(respuesta, "Agotamiento de recursos no renovables")
        self.assertContains(respuesta, "Significativo")
        self.assertContains(respuesta, "No significativo")
        self.assertContains(respuesta, "IND-ENE-01")

    def test_catalogo_muestra_alerta_significativo_sin_indicador(self):
        AspectoAmbiental.objects.create(
            proceso=self.proceso,
            codigo="ASP-04",
            nombre="Emisiones por planta eléctrica de emergencia",
            impacto_asociado="Emisiones de gases de efecto invernadero",
            es_significativo=True,
            criterio_significancia="Operación no programada con potencial de emisión",
        )
        respuesta = self.cliente.get(reverse("ambiental:catalogo"))
        self.assertContains(respuesta, "Aspecto significativo sin indicador")
        self.assertContains(respuesta, "ASP-04")
        self.assertContains(respuesta, "no bloquea el registro")

    def test_catalogo_sin_alerta_cuando_significativo_tiene_indicador(self):
        respuesta = self.cliente.get(reverse("ambiental:catalogo"))
        self.assertNotContains(respuesta, "Aspecto significativo sin indicador")

    def test_filtro_significativos(self):
        respuesta = self.cliente.get(reverse("ambiental:catalogo"), {"significancia": "significativos"})
        self.assertContains(respuesta, "ASP-01")
        self.assertNotContains(respuesta, "ASP-02")

    def test_filtro_no_significativos(self):
        respuesta = self.cliente.get(reverse("ambiental:catalogo"), {"significancia": "no_significativos"})
        self.assertContains(respuesta, "ASP-02")
        self.assertNotContains(respuesta, "ASP-01")

    def test_filtro_invalido_muestra_todos(self):
        respuesta = self.cliente.get(reverse("ambiental:catalogo"), {"significancia": "inventado"})
        self.assertContains(respuesta, "ASP-01")
        self.assertContains(respuesta, "ASP-02")

    def test_estado_vacio_procesos(self):
        Indicador.objects.all().delete()
        AspectoAmbiental.objects.all().delete()
        Proceso.objects.all().delete()
        respuesta = self.cliente.get(reverse("ambiental:catalogo"))
        self.assertContains(respuesta, "Aún no hay procesos registrados")
        self.assertContains(respuesta, "Aún no hay aspectos registrados")


class FormularioProcesoPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        crear_usuario(username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA)
        cls.cliente = Client()
        cls.cliente.login(username="fcastro", password=cls.clave)

    def test_formulario_renderiza(self):
        respuesta = self.cliente.get(reverse("ambiental:proceso_nuevo"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Nuevo proceso")
        self.assertContains(respuesta, "Código")

    def test_crear_proceso_valido(self):
        respuesta = self.cliente.post(
            reverse("ambiental:proceso_nuevo"),
            {"codigo": "PR-02", "nombre": "Servicios generales", "responsable": "Laura Gómez"},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Proceso.objects.filter(codigo="PR-02").exists())
        self.assertContains(respuesta, "Proceso PR-02 creado.")

    def test_crear_proceso_vacio_no_guarda_y_muestra_errores(self):
        respuesta = self.cliente.post(reverse("ambiental:proceso_nuevo"), {})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ingrese el código del proceso.")
        self.assertContains(respuesta, "Ingrese el nombre del proceso.")
        self.assertContains(respuesta, "Ingrese el responsable del proceso.")
        self.assertFalse(Proceso.objects.exists())

    def test_crear_proceso_duplicado_no_guarda(self):
        servicios.crear_proceso(codigo="PR-01", nombre="Existente", responsable="Responsable")
        respuesta = self.cliente.post(
            reverse("ambiental:proceso_nuevo"),
            {"codigo": "PR-01", "nombre": "Duplicado", "responsable": "Otro"},
        )
        self.assertContains(respuesta, "Ya existe un proceso con ese código.")
        self.assertEqual(Proceso.objects.count(), 1)


class FormularioAspectoPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        crear_usuario(username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA)
        cls.proceso = servicios.crear_proceso(
            codigo="PR-01", nombre="Operación de infraestructura TI", responsable="Carlos Martínez"
        )
        cls.cliente = Client()
        cls.cliente.login(username="fcastro", password=cls.clave)

    def test_formulario_renderiza(self):
        respuesta = self.cliente.get(reverse("ambiental:aspecto_nuevo"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Nuevo aspecto ambiental")
        self.assertContains(respuesta, "Impacto asociado")
        self.assertContains(respuesta, "Dictamen de significancia")

    def test_crear_aspecto_valido_significativo(self):
        respuesta = self.cliente.post(
            reverse("ambiental:aspecto_nuevo"),
            {
                "proceso": str(self.proceso.pk),
                "codigo": "ASP-01",
                "nombre": "Consumo de energía eléctrica",
                "impacto_asociado": "Agotamiento de recursos no renovables",
                "es_significativo": "1",
                "criterio_significancia": "Uso por encima del umbral interno",
            },
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        aspecto = AspectoAmbiental.objects.get(codigo="ASP-01")
        self.assertTrue(aspecto.es_significativo)
        self.assertContains(respuesta, "Aspecto ASP-01 creado.")

    def test_crear_aspecto_no_significativo(self):
        self.cliente.post(
            reverse("ambiental:aspecto_nuevo"),
            {
                "proceso": str(self.proceso.pk),
                "codigo": "ASP-02",
                "nombre": "Consumo de agua potable",
                "impacto_asociado": "Presión sobre el recurso hídrico local",
                "es_significativo": "0",
                "criterio_significancia": "Dentro del rango esperado",
            },
        )
        self.assertFalse(AspectoAmbiental.objects.get(codigo="ASP-02").es_significativo)

    def test_crear_aspecto_sin_impacto_no_guarda(self):
        respuesta = self.cliente.post(
            reverse("ambiental:aspecto_nuevo"),
            {
                "proceso": str(self.proceso.pk),
                "codigo": "ASP-03",
                "nombre": "Sin impacto",
                "impacto_asociado": "",
                "es_significativo": "1",
                "criterio_significancia": "Criterio",
            },
        )
        self.assertContains(respuesta, "Describa el impacto asociado.")
        self.assertFalse(AspectoAmbiental.objects.filter(codigo="ASP-03").exists())

    def test_crear_aspecto_sin_dictamen_no_guarda(self):
        respuesta = self.cliente.post(
            reverse("ambiental:aspecto_nuevo"),
            {
                "proceso": str(self.proceso.pk),
                "codigo": "ASP-04",
                "nombre": "Sin dictamen",
                "impacto_asociado": "Impacto",
                "es_significativo": "",
                "criterio_significancia": "Criterio",
            },
        )
        self.assertContains(respuesta, "Elija el dictamen de significancia.")
        self.assertFalse(AspectoAmbiental.objects.filter(codigo="ASP-04").exists())

    def test_crear_aspecto_significativo_sin_indicador_no_bloquea(self):
        respuesta = self.cliente.post(
            reverse("ambiental:aspecto_nuevo"),
            {
                "proceso": str(self.proceso.pk),
                "codigo": "ASP-05",
                "nombre": "Emisiones planta de emergencia",
                "impacto_asociado": "Emisiones de gases",
                "es_significativo": "1",
                "criterio_significancia": "Operación no programada",
            },
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(AspectoAmbiental.objects.filter(codigo="ASP-05").exists())
