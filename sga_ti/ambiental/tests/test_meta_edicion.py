import secrets
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ambiental import servicios
from ambiental.models import AspectoAmbiental, Indicador, MetaAmbiental, Proceso
from cuentas.models import Usuario
from cuentas.servicios import crear_usuario
from operacion import servicios as operacion_servicios

ANIO = timezone.now().year


def preparar_meta():
    proceso = Proceso.objects.create(
        codigo="PR-01", nombre="Operación TI", responsable="Carlos Martínez"
    )
    aspecto = AspectoAmbiental.objects.create(
        proceso=proceso,
        codigo="ASP-01",
        nombre="Consumo de energía eléctrica",
        impacto_asociado="Agotamiento de recursos no renovables",
        es_significativo=True,
        criterio_significancia="Uso por encima del umbral interno",
    )
    indicador = Indicador.objects.create(
        aspecto=aspecto,
        codigo="IND-ENE-01",
        nombre="Energía eléctrica",
        unidad_medida="kWh",
        periodicidad="Mensual",
    )
    meta = servicios.crear_meta(
        indicador=indicador,
        anio_vigencia=ANIO,
        valor_limite=Decimal("8500.00"),
        umbral_advertencia_pct=90,
    )
    return indicador, meta


class MetaEdicionPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        cls.responsable = crear_usuario(
            username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA
        )
        cls.operador = crear_usuario(
            username="keiner", password=cls.clave, rol=Usuario.Rol.OPERADOR
        )
        cls.indicador, cls.meta = preparar_meta()

    def setUp(self):
        self.cliente = Client()
        self.cliente.login(username="fcastro", password=self.clave)
        self.url = reverse("ambiental:meta_editar", args=[self.meta.pk])

    def test_formulario_renderiza(self):
        respuesta = self.cliente.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "IND-ENE-01")
        self.assertContains(respuesta, str(ANIO))
        self.assertContains(respuesta, "Valor de activación")

    def test_actualiza_limite_y_umbral(self):
        respuesta = self.cliente.post(
            self.url, {"valor_limite": "9000.00", "umbral_advertencia_pct": "80"}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_limite, Decimal("9000.00"))
        self.assertEqual(self.meta.umbral_advertencia_pct, 80)
        self.assertEqual(self.meta.valor_activacion, Decimal("7200.00"))

    def test_rechaza_umbral_fuera_de_rango(self):
        respuesta = self.cliente.post(
            self.url, {"valor_limite": "9000.00", "umbral_advertencia_pct": "40"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "entre 50% y 99%")
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.umbral_advertencia_pct, 90)

    def test_rechaza_limite_no_positivo(self):
        respuesta = self.cliente.post(
            self.url, {"valor_limite": "0", "umbral_advertencia_pct": "90"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "El límite mensual debe ser numéricamente positivo.")
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_limite, Decimal("8500.00"))

    def test_no_cambia_el_snapshot_de_mediciones(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.indicador,
            anio=ANIO,
            mes=8,
            valor_medido="8000.00",
            evidencia="Factura EE-08",
        )
        self.cliente.post(
            self.url, {"valor_limite": "7000.00", "umbral_advertencia_pct": "80"}
        )
        medicion.refresh_from_db()
        self.assertEqual(medicion.valor_meta, Decimal("8500.00"))
        self.assertEqual(medicion.estado_semaforo, "ADVERTENCIA")

    def test_operador_denegado(self):
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        self.assertEqual(operador.get(self.url).status_code, 403)
        respuesta = operador.post(
            self.url, {"valor_limite": "9000.00", "umbral_advertencia_pct": "80"}
        )
        self.assertEqual(respuesta.status_code, 403)
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.umbral_advertencia_pct, 90)

    def test_anonimo_redirige(self):
        respuesta = Client().get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("cuentas:entrada"), respuesta.url)

    def test_enlace_editar_en_la_tabla(self):
        respuesta = self.cliente.get(reverse("ambiental:parametrizacion"))
        self.assertContains(respuesta, self.url)
        self.assertContains(respuesta, "Editar")
