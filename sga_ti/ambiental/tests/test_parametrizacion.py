import secrets
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ambiental.models import AspectoAmbiental, Indicador, MetaAmbiental, Proceso
from ambiental import servicios
from cuentas.models import Usuario
from cuentas.servicios import crear_usuario

ANIO = timezone.now().year


def preparar_ambiente():
    proceso = Proceso.objects.create(codigo="PR-01", nombre="Operación TI", responsable="Carlos Martínez")
    aspecto = AspectoAmbiental.objects.create(
        proceso=proceso,
        codigo="ASP-01",
        nombre="Consumo de energía eléctrica",
        impacto_asociado="Agotamiento de recursos no renovables",
        es_significativo=True,
        criterio_significancia="Uso por encima del umbral interno",
    )
    indicador_con_meta = Indicador.objects.create(
        aspecto=aspecto, codigo="IND-ENE-01", nombre="Consumo mensual de energía", unidad_medida="kWh", periodicidad="Mensual"
    )
    meta = MetaAmbiental.objects.create(
        indicador=indicador_con_meta,
        anio_vigencia=ANIO,
        valor_limite="8500.00",
        operador="<=",
        umbral_advertencia_pct=90,
    )
    indicador_sin_meta = Indicador.objects.create(
        aspecto=aspecto, codigo="IND-AGU-02", nombre="Consumo de agua", unidad_medida="m3", periodicidad="Mensual"
    )
    return aspecto, indicador_con_meta, indicador_sin_meta, meta


class ParametrizacionPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        crear_usuario(username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA)
        cls.aspecto, cls.indicador_con_meta, cls.indicador_sin_meta, cls.meta = preparar_ambiente()
        cls.cliente = Client()
        cls.cliente.login(username="fcastro", password=cls.clave)

    def test_parametrizacion_muestra_indicadores_y_meta(self):
        respuesta = self.cliente.get(reverse("ambiental:parametrizacion"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "IND-ENE-01")
        self.assertContains(respuesta, "Consumo mensual de energía")
        self.assertContains(respuesta, "8500,00")
        self.assertContains(respuesta, "umbral 90%")
        self.assertContains(respuesta, "7650,00")
        self.assertContains(respuesta, "Parametrizado")

    def test_parametrizacion_muestra_indicador_sin_meta(self):
        respuesta = self.cliente.get(reverse("ambiental:parametrizacion"))
        self.assertContains(respuesta, "IND-AGU-02")
        self.assertContains(respuesta, "Sin meta")
        self.assertContains(respuesta, "Asignar meta")

    def test_parametrizacion_alerta_sin_meta_vigente(self):
        respuesta = self.cliente.get(reverse("ambiental:parametrizacion"))
        self.assertContains(respuesta, "Indicador sin meta vigente")
        self.assertContains(respuesta, "1 indicador")

    def test_parametrizacion_sin_alerta_si_todos_tienen_meta(self):
        MetaAmbiental.objects.create(
            indicador=self.indicador_sin_meta,
            anio_vigencia=ANIO,
            valor_limite="350.00",
            operador="<=",
            umbral_advertencia_pct=90,
        )
        respuesta = self.cliente.get(reverse("ambiental:parametrizacion"))
        self.assertNotContains(respuesta, "Indicador sin meta vigente")

    def test_filtro_anio_muestra_sin_meta_en_anio_sin_registros(self):
        respuesta = self.cliente.get(
            reverse("ambiental:parametrizacion"), {"anio": ANIO + 1}
        )
        self.assertContains(respuesta, "Sin meta")
        self.assertNotContains(respuesta, "7650,00")
        self.assertNotContains(respuesta, "Parametrizado")

    def test_filtro_anio_invalido_usa_anio_actual(self):
        respuesta = self.cliente.get(reverse("ambiental:parametrizacion"), {"anio": "abc"})
        self.assertContains(respuesta, "8500,00")

    def test_estado_vacio_sin_indicadores(self):
        MetaAmbiental.objects.all().delete()
        Indicador.objects.all().delete()
        respuesta = self.cliente.get(reverse("ambiental:parametrizacion"))
        self.assertContains(respuesta, "Aún no hay indicadores registrados")


class FormularioIndicadorPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        crear_usuario(username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA)
        cls.aspecto, _, _, _ = preparar_ambiente()
        cls.cliente = Client()
        cls.cliente.login(username="fcastro", password=cls.clave)

    def test_formulario_renderiza(self):
        respuesta = self.cliente.get(reverse("ambiental:indicador_nuevo"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Nuevo indicador")
        self.assertContains(respuesta, "Unidad de medida")
        self.assertContains(respuesta, "Periodicidad")

    def test_crear_indicador_valido(self):
        respuesta = self.cliente.post(
            reverse("ambiental:indicador_nuevo"),
            {
                "aspecto": str(self.aspecto.pk),
                "codigo": "IND-RAE-03",
                "nombre": "Residuos RAEE",
                "unidad_medida": "kg",
                "periodicidad": "Mensual",
            },
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(Indicador.objects.filter(codigo="IND-RAE-03").exists())
        self.assertContains(respuesta, "Indicador IND-RAE-03 creado.")

    def test_crear_indicador_sin_unidad_no_guarda(self):
        respuesta = self.cliente.post(
            reverse("ambiental:indicador_nuevo"),
            {
                "aspecto": str(self.aspecto.pk),
                "codigo": "IND-09",
                "nombre": "Sin unidad",
                "unidad_medida": "",
                "periodicidad": "Mensual",
            },
        )
        self.assertContains(respuesta, "Ingrese la unidad de medida del indicador.")
        self.assertFalse(Indicador.objects.filter(codigo="IND-09").exists())

    def test_crear_indicador_duplicado_no_guarda(self):
        respuesta = self.cliente.post(
            reverse("ambiental:indicador_nuevo"),
            {
                "aspecto": str(self.aspecto.pk),
                "codigo": "IND-ENE-01",
                "nombre": "Duplicado",
                "unidad_medida": "kWh",
                "periodicidad": "Mensual",
            },
        )
        self.assertContains(respuesta, "Ya existe un indicador con ese código.")
        self.assertEqual(Indicador.objects.filter(codigo="IND-ENE-01").count(), 1)


class FormularioMetaPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        crear_usuario(username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA)
        _, _, cls.indicador_sin_meta, _ = preparar_ambiente()
        cls.cliente = Client()
        cls.cliente.login(username="fcastro", password=cls.clave)

    def test_formulario_renderiza(self):
        respuesta = self.cliente.get(reverse("ambiental:meta_nueva"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Nueva meta")
        self.assertContains(respuesta, "Límite mensual permitido")
        self.assertContains(respuesta, "Umbral de advertencia")

    def test_crear_meta_valida_no_expone_operador(self):
        respuesta = self.cliente.post(
            reverse("ambiental:meta_nueva"),
            {
                "indicador": str(self.indicador_sin_meta.pk),
                "anio_vigencia": str(ANIO),
                "valor_limite": "350.00",
                "umbral_advertencia_pct": "90",
            },
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)
        meta = MetaAmbiental.objects.get(indicador=self.indicador_sin_meta, anio_vigencia=ANIO)
        self.assertEqual(meta.operador, "<=")
        self.assertEqual(meta.valor_limite, Decimal("350.00"))
        self.assertContains(respuesta, "Meta %s creada" % ANIO)

    def test_crear_meta_umbral_fuera_de_rango_no_guarda(self):
        respuesta = self.cliente.post(
            reverse("ambiental:meta_nueva"),
            {
                "indicador": str(self.indicador_sin_meta.pk),
                "anio_vigencia": str(ANIO),
                "valor_limite": "350.00",
                "umbral_advertencia_pct": "100",
            },
        )
        self.assertContains(respuesta, "El umbral de advertencia debe estar entre 50% y 99%.")
        self.assertFalse(MetaAmbiental.objects.filter(indicador=self.indicador_sin_meta).exists())

    def test_crear_meta_valor_negativo_no_guarda(self):
        respuesta = self.cliente.post(
            reverse("ambiental:meta_nueva"),
            {
                "indicador": str(self.indicador_sin_meta.pk),
                "anio_vigencia": str(ANIO),
                "valor_limite": "-5",
                "umbral_advertencia_pct": "90",
            },
        )
        self.assertContains(respuesta, "El límite mensual debe ser numéricamente positivo.")
        self.assertFalse(MetaAmbiental.objects.filter(indicador=self.indicador_sin_meta).exists())

    def test_preseleccion_de_indicador_por_get(self):
        respuesta = self.cliente.get(
            reverse("ambiental:meta_nueva"), {"indicador": str(self.indicador_sin_meta.pk)}
        )
        self.assertEqual(respuesta.context["form"].initial.get("indicador"), self.indicador_sin_meta.pk)

    def test_preseleccion_con_identificador_invalido_no_falla(self):
        respuesta = self.cliente.get(
            reverse("ambiental:meta_nueva"), {"indicador": "no-es-uuid"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["form"].initial.get("indicador"))
