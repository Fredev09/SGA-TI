from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from operacion import servicios
from operacion.models import AuditoriaMedicion, Medicion
from operacion.tests.utilidades import ANIO, crear_usuarios, preparar_catalogo

PASO_UNO = {"paso": "1"}
PASO_DOS = {"paso": "2"}
PASO_TRES = {"paso": "3"}


class PermisosMedicionPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()
        cls.medicion = servicios.registrar_medicion(
            usuario=cls.responsable,
            indicador=cls.datos["agua"],
            anio=ANIO,
            mes=9,
            valor_medido="310.00",
            evidencia="Recibo de acueducto 09",
        )

    def setUp(self):
        self.anonimo = Client()
        self.operador_cliente = Client()
        self.operador_cliente.login(username="keiner", password=self.clave)
        self.responsable_cliente = Client()
        self.responsable_cliente.login(username="fcastro", password=self.clave)

    def test_anonimo_es_redirigido_a_la_entrada(self):
        urls = [
            reverse("operacion:medicion_nueva"),
            reverse("operacion:medicion_editar", args=[self.medicion.pk]),
        ]
        for url in urls:
            respuesta = self.anonimo.get(url)
            self.assertEqual(respuesta.status_code, 302, url)
            self.assertIn(reverse("cuentas:entrada"), respuesta.url, url)

    def test_ambos_roles_pueden_abrir_el_asistente(self):
        for cliente in (self.operador_cliente, self.responsable_cliente):
            respuesta = cliente.get(reverse("operacion:medicion_nueva"))
            self.assertEqual(respuesta.status_code, 200)

    def test_paso_uno_sugiere_el_anio_en_curso(self):
        respuesta = self.operador_cliente.get(reverse("operacion:medicion_nueva"))
        self.assertEqual(
            respuesta.context["form_periodo"].initial["anio"], timezone.now().year
        )

    def test_solo_el_responsable_puede_abrir_la_edicion(self):
        url = reverse("operacion:medicion_editar", args=[self.medicion.pk])
        self.assertEqual(self.operador_cliente.get(url).status_code, 403)
        self.assertEqual(self.responsable_cliente.get(url).status_code, 200)

    def test_el_operador_no_ve_el_enlace_de_edicion(self):
        url = reverse("operacion:medicion_editar", args=[self.medicion.pk])
        respuesta = self.operador_cliente.get(reverse("core:inicio"))
        self.assertNotContains(respuesta, url)

    def test_el_responsable_ve_el_enlace_de_edicion(self):
        url = reverse("operacion:medicion_editar", args=[self.medicion.pk])
        respuesta = self.responsable_cliente.get(reverse("core:inicio"))
        self.assertContains(respuesta, url)

    def test_edicion_muestra_el_primer_paso(self):
        respuesta = self.responsable_cliente.get(
            reverse("operacion:medicion_editar", args=[self.medicion.pk])
        )
        self.assertContains(respuesta, "Indicador y periodo")
        self.assertContains(respuesta, "Siguiente")
        self.assertNotContains(respuesta, "Guardar medición")

    def test_edicion_paso_uno_muestra_el_formulario_de_valor(self):
        respuesta = self.responsable_cliente.post(
            reverse("operacion:medicion_editar", args=[self.medicion.pk]),
            {"paso": "1"},
        )
        self.assertContains(respuesta, "Valor y evidencia")
        self.assertContains(respuesta, 'name="valor_medido"')
        self.assertEqual(AuditoriaMedicion.objects.count(), 0)

    def test_edicion_paso_dos_muestra_confirmacion_sin_guardar(self):
        respuesta = self.responsable_cliente.post(
            reverse("operacion:medicion_editar", args=[self.medicion.pk]),
            {
                "paso": "2",
                "valor_medido": "320.00",
                "evidencia": "Recibo de acueducto 09",
            },
        )
        self.assertContains(respuesta, "Confirmación y guardado")
        self.assertContains(respuesta, "Valor nuevo")
        self.assertEqual(AuditoriaMedicion.objects.count(), 0)
        self.medicion.refresh_from_db()
        self.assertEqual(self.medicion.valor_medido, Decimal("310.00"))

    def test_edicion_paso_tres_guarda_y_registra_bitacora(self):
        respuesta = self.responsable_cliente.post(
            reverse("operacion:medicion_editar", args=[self.medicion.pk]),
            {
                "paso": "3",
                "valor_medido": "320.00",
                "evidencia": "Recibo de acueducto 09",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(AuditoriaMedicion.objects.count(), 1)
        self.medicion.refresh_from_db()
        self.assertEqual(self.medicion.valor_medido, Decimal("320.00"))

    def test_edicion_paso_dos_invalido_no_avanza(self):
        respuesta = self.responsable_cliente.post(
            reverse("operacion:medicion_editar", args=[self.medicion.pk]),
            {
                "paso": "2",
                "valor_medido": "-5",
                "evidencia": "Recibo corregido",
            },
        )
        self.assertContains(respuesta, "Valor y evidencia")
        self.assertEqual(AuditoriaMedicion.objects.count(), 0)
        self.medicion.refresh_from_db()
        self.assertEqual(self.medicion.valor_medido, Decimal("310.00"))

    def test_edicion_atras_desde_confirmacion_vuelve_al_valor(self):
        respuesta = self.responsable_cliente.post(
            reverse("operacion:medicion_editar", args=[self.medicion.pk]),
            {
                "paso": "3",
                "volver": "2",
                "valor_medido": "320.00",
                "evidencia": "Recibo de acueducto 09",
            },
        )
        self.assertContains(respuesta, "Valor y evidencia")
        self.assertEqual(AuditoriaMedicion.objects.count(), 0)

    def test_flujo_completo_de_tres_pasos(self):
        url = reverse("operacion:medicion_nueva")
        datos = {
            "indicador": str(self.datos["energia"].pk),
            "anio": str(ANIO),
            "mes": "10",
        }
        respuesta = self.operador_cliente.post(url, dict(PASO_UNO, **datos))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Valor y evidencia")

        respuesta = self.operador_cliente.post(
            url,
            dict(
                PASO_DOS,
                **datos,
                valor_medido="7000",
                evidencia="Factura EE-2026-10",
            ),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Confirmación y guardado")
        self.assertContains(respuesta, "Normal")

        respuesta = self.operador_cliente.post(
            url,
            dict(
                PASO_TRES,
                **datos,
                valor_medido="7000",
                evidencia="Factura EE-2026-10",
            ),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Medicion.objects.filter(mes=10, anio=ANIO).exists())

    def test_volver_desde_el_paso_dos_regresa_al_periodo(self):
        url = reverse("operacion:medicion_nueva")
        datos = {
            "indicador": str(self.datos["energia"].pk),
            "anio": str(ANIO),
            "mes": "10",
        }
        respuesta = self.operador_cliente.post(url, dict(PASO_DOS, volver="1", **datos))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Indicador y periodo")
        self.assertContains(respuesta, str(self.datos["energia"].pk))

    def test_registro_directo_al_paso_final_se_valida_en_servidor(self):
        url = reverse("operacion:medicion_nueva")
        respuesta = self.operador_cliente.post(
            url,
            dict(
                PASO_TRES,
                indicador=str(self.datos["energia"].pk),
                anio=str(ANIO),
                mes="11",
                valor_medido="-5",
                evidencia="Factura EE-2026-11",
            ),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Medicion.objects.filter(mes=11).exists())

    def test_registro_directo_sin_evidencia_no_guarda(self):
        url = reverse("operacion:medicion_nueva")
        respuesta = self.operador_cliente.post(
            url,
            dict(
                PASO_TRES,
                indicador=str(self.datos["energia"].pk),
                anio=str(ANIO),
                mes="11",
                valor_medido="7000",
                evidencia="",
            ),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Medicion.objects.filter(mes=11).exists())

    def test_edicion_directa_con_valor_invalido_no_guarda(self):
        url = reverse("operacion:medicion_editar", args=[self.medicion.pk])
        respuesta = self.responsable_cliente.post(
            url, {"valor_medido": "-5", "evidencia": "Recibo corregido"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.medicion.refresh_from_db()
        self.assertEqual(self.medicion.valor_medido, Decimal("310.00"))
        self.assertEqual(AuditoriaMedicion.objects.count(), 0)

    def test_el_operador_no_puede_editar_por_post_directo(self):
        url = reverse("operacion:medicion_editar", args=[self.medicion.pk])
        respuesta = self.operador_cliente.post(
            url, {"valor_medido": "320.00", "evidencia": "Recibo corregido"}
        )
        self.assertEqual(respuesta.status_code, 403)
        self.medicion.refresh_from_db()
        self.assertEqual(self.medicion.valor_medido, Decimal("310.00"))
        self.assertEqual(AuditoriaMedicion.objects.count(), 0)

    def test_edicion_valida_registra_bitacora_y_redirige(self):
        url = reverse("operacion:medicion_editar", args=[self.medicion.pk])
        respuesta = self.responsable_cliente.post(
            url, {"valor_medido": "320.00", "evidencia": "Recibo de acueducto 09"}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(AuditoriaMedicion.objects.count(), 1)
        self.medicion.refresh_from_db()
        self.assertEqual(self.medicion.valor_medido, Decimal("320.00"))

    def test_identificador_de_medicion_invalido_da_404(self):
        respuesta = self.responsable_cliente.get("/mediciones/no-es-uuid/editar/")
        self.assertEqual(respuesta.status_code, 404)

    def test_medicion_inexistente_da_404(self):
        respuesta = self.responsable_cliente.get(
            reverse(
                "operacion:medicion_editar",
                args=["11111111-1111-1111-1111-111111111111"],
            )
        )
        self.assertEqual(respuesta.status_code, 404)
