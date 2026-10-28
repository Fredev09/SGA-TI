import secrets
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ambiental import servicios
from ambiental.models import (
    AspectoAmbiental,
    AuditoriaMeta,
    Indicador,
    MetaAmbiental,
    Proceso,
)
from cuentas.models import Usuario
from cuentas.servicios import crear_usuario
from gestion.models import NoConformidad
from operacion import servicios as operacion_servicios
from operacion.models import AuditoriaEvaluacion

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
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Confirmar recálculo")
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_limite, Decimal("8500.00"))

        respuesta = self.cliente.post(
            self.url,
            {
                "confirmado": "1",
                "valor_limite": "9000.00",
                "umbral_advertencia_pct": "80",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_limite, Decimal("9000.00"))
        self.assertEqual(self.meta.umbral_advertencia_pct, 80)
        self.assertEqual(self.meta.valor_activacion, Decimal("7200.00"))
        auditoria = AuditoriaMeta.objects.get(meta=self.meta)
        self.assertEqual(auditoria.valor_anterior, Decimal("8500.00"))
        self.assertEqual(auditoria.valor_nuevo, Decimal("9000.00"))
        self.assertEqual(auditoria.umbral_anterior, 90)
        self.assertEqual(auditoria.umbral_nuevo, 80)
        self.assertEqual(auditoria.mediciones_recalculadas, 0)

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

    def _confirmar(self, valor, umbral):
        self.cliente.post(
            self.url, {"valor_limite": valor, "umbral_advertencia_pct": umbral}
        )
        return self.cliente.post(
            self.url,
            {
                "confirmado": "1",
                "valor_limite": valor,
                "umbral_advertencia_pct": umbral,
            },
        )

    def test_la_confirmacion_no_guarda_ni_recalcula(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.indicador,
            anio=ANIO,
            mes=8,
            valor_medido="8000.00",
            evidencia="Factura EE-08",
        )
        respuesta = self.cliente.post(
            self.url, {"valor_limite": "7000.00", "umbral_advertencia_pct": "80"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Se recalculará 1 medición")
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_limite, Decimal("8500.00"))
        medicion.refresh_from_db()
        self.assertEqual(medicion.valor_meta, Decimal("8500.00"))
        self.assertEqual(AuditoriaMeta.objects.count(), 0)
        self.assertEqual(AuditoriaEvaluacion.objects.count(), 0)

    def test_confirma_y_recalcula_las_mediciones(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.indicador,
            anio=ANIO,
            mes=8,
            valor_medido="8000.00",
            evidencia="Factura EE-08",
        )
        respuesta = self._confirmar("7000.00", "80")
        self.assertEqual(respuesta.status_code, 302)
        medicion.refresh_from_db()
        self.assertEqual(medicion.valor_meta, Decimal("7000.00"))
        self.assertEqual(medicion.desvio_pct, Decimal("14.29"))
        self.assertEqual(medicion.estado_semaforo, "ALERTA")
        auditoria = AuditoriaEvaluacion.objects.get(medicion=medicion)
        self.assertEqual(auditoria.estado_anterior, "ADVERTENCIA")
        self.assertEqual(auditoria.estado_nuevo, "ALERTA")
        self.assertEqual(auditoria.valor_meta_anterior, Decimal("8500.00"))
        self.assertEqual(auditoria.valor_meta_nuevo, Decimal("7000.00"))
        self.assertTrue(NoConformidad.objects.filter(medicion=medicion).exists())

    def test_recalcula_todas_las_mediciones_del_anio(self):
        primera = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.indicador,
            anio=ANIO,
            mes=7,
            valor_medido="8000.00",
            evidencia="Factura EE-07",
        )
        segunda = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.indicador,
            anio=ANIO,
            mes=8,
            valor_medido="8100.00",
            evidencia="Factura EE-08",
        )
        self._confirmar("7000.00", "80")
        for medicion in (primera, segunda):
            medicion.refresh_from_db()
            self.assertEqual(medicion.valor_meta, Decimal("7000.00"))
            self.assertEqual(medicion.estado_semaforo, "ALERTA")
        self.assertEqual(AuditoriaEvaluacion.objects.count(), 2)
        auditoria = AuditoriaMeta.objects.get(meta=self.meta)
        self.assertEqual(auditoria.mediciones_recalculadas, 2)

    def test_reevalua_la_no_conformidad_a_revision(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.indicador,
            anio=ANIO,
            mes=8,
            valor_medido="8900.00",
            evidencia="Factura EE-08",
        )
        no_conformidad = NoConformidad.objects.get(medicion=medicion)
        self.assertEqual(no_conformidad.requiere_revision, False)
        self._confirmar("10000.00", "90")
        medicion.refresh_from_db()
        no_conformidad.refresh_from_db()
        self.assertEqual(medicion.estado_semaforo, "NORMAL")
        self.assertTrue(no_conformidad.requiere_revision)

    def test_sin_mediciones_guarda_la_meta_y_audita(self):
        respuesta = self._confirmar("9000.00", "80")
        self.assertEqual(respuesta.status_code, 302)
        self.meta.refresh_from_db()
        self.assertEqual(self.meta.valor_limite, Decimal("9000.00"))
        auditoria = AuditoriaMeta.objects.get(meta=self.meta)
        self.assertEqual(auditoria.mediciones_recalculadas, 0)
        self.assertEqual(AuditoriaEvaluacion.objects.count(), 0)

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
