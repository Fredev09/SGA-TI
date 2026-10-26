import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from gestion import servicios
from gestion.models import (
    AccionCorrectiva,
    EvidenciaNoConformidad,
    NoConformidad,
    TransicionNoConformidad,
)
from operacion import servicios as operacion_servicios
from operacion.models import AuditoriaMedicion, Medicion
from operacion.tests.utilidades import ANIO, crear_usuarios, preparar_catalogo

DIR_EVIDENCIAS = Path(tempfile.mkdtemp(prefix="sga_evidencias_pruebas_"))
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"


@override_settings(EVIDENCIAS_RUTA=str(DIR_EVIDENCIAS))
class CicloNoConformidadPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(DIR_EVIDENCIAS, ignore_errors=True)

    def setUp(self):
        self.cliente = Client()
        self.cliente.login(username="fcastro", password=self.clave)

    def _hallazgo(self, **extras):
        datos = {
            "usuario": self.responsable,
            "origen": "MANUAL",
            "descripcion": "Fuga de agua en instalaciones sanitarias",
            "severidad": "Media",
        }
        datos.update(extras)
        return servicios.crear_manual(**datos)

    def _evidencia(self, no_conformidad, nombre="acta.pdf", contenido=PDF):
        archivo = SimpleUploadedFile(nombre, contenido, content_type="application/pdf")
        return servicios.adjuntar_evidencia(
            no_conformidad=no_conformidad,
            archivo=archivo,
            referencia="Acta de mantenimiento 2026-10",
            usuario=self.responsable,
        )

    def _completo(self):
        no_conformidad = self._hallazgo()
        servicios.registrar_causa_raiz(
            no_conformidad=no_conformidad,
            causa_raiz="Empalme sin sellar en el baño del bloque administrativo",
            usuario=self.responsable,
        )
        accion = servicios.crear_accion(
            no_conformidad=no_conformidad,
            descripcion_accion="Sellar el empalme y verificar presión",
            responsable="Laura Gómez",
            fecha_limite=timezone.now().date() + timedelta(days=5),
            usuario=self.responsable,
        )
        servicios.actualizar_accion(
            accion=accion,
            ejecutada=True,
            evaluacion_eficacia="Sin fugas durante dos semanas de seguimiento",
            es_eficaz=True,
        )
        self._evidencia(no_conformidad)
        return no_conformidad

    def test_crear_manual_genera_codigo_y_transicion_inicial(self):
        no_conformidad = self._hallazgo(origen="AUDITORIA")
        self.assertEqual(no_conformidad.codigo, "NC-%s-01" % ANIO)
        self.assertEqual(no_conformidad.estado, "ABIERTA")
        self.assertEqual(no_conformidad.transiciones.count(), 1)
        self.assertEqual(no_conformidad.transiciones.first().estado_nuevo, "ABIERTA")

    def test_crear_manual_rechaza_origen_automatica(self):
        with self.assertRaises(ValidationError):
            self._hallazgo(origen="AUTOMATICA")
        self.assertFalse(NoConformidad.objects.exists())

    def test_causa_raiz_mueve_a_en_analisis(self):
        no_conformidad = self._hallazgo()
        servicios.registrar_causa_raiz(
            no_conformidad=no_conformidad,
            causa_raiz="Falta de mantenimiento preventivo",
            usuario=self.responsable,
        )
        no_conformidad.refresh_from_db()
        self.assertEqual(no_conformidad.estado, "EN_ANALISIS")
        self.assertEqual(no_conformidad.transiciones.last().estado_nuevo, "EN_ANALISIS")

    def test_causa_raiz_vacia_es_rechazada(self):
        no_conformidad = self._hallazgo()
        with self.assertRaises(ValidationError):
            servicios.registrar_causa_raiz(
                no_conformidad=no_conformidad, causa_raiz="   ", usuario=self.responsable
            )

    def test_accion_exige_fecha_limite(self):
        no_conformidad = self._hallazgo()
        with self.assertRaises(ValidationError):
            servicios.crear_accion(
                no_conformidad=no_conformidad,
                descripcion_accion="Acción",
                responsable="Laura",
                fecha_limite=None,
                usuario=self.responsable,
            )

    def test_eficacia_exige_ejecucion(self):
        accion = AccionCorrectiva.objects.create(
            no_conformidad=self._hallazgo(),
            descripcion_accion="Revisar",
            responsable="Laura",
            fecha_limite=timezone.now().date(),
        )
        with self.assertRaises(ValidationError):
            servicios.actualizar_accion(
                accion=accion,
                ejecutada=False,
                evaluacion_eficacia="Documentada",
                es_eficaz=True,
            )

    def test_eficacia_exige_evaluacion_documentada(self):
        accion = AccionCorrectiva.objects.create(
            no_conformidad=self._hallazgo(),
            descripcion_accion="Revisar",
            responsable="Laura",
            fecha_limite=timezone.now().date(),
        )
        with self.assertRaises(ValidationError):
            servicios.actualizar_accion(
                accion=accion, ejecutada=True, evaluacion_eficacia="  ", es_eficaz=True
            )

    def test_cierre_rechaza_sin_causa_raiz(self):
        no_conformidad = self._hallazgo()
        with self.assertRaises(ValidationError) as error:
            servicios.cerrar_no_conformidad(
                no_conformidad=no_conformidad, usuario=self.responsable
            )
        self.assertIn("causa raíz", " ".join(error.exception.messages))

    def test_cierre_rechaza_sin_accion_ejecutada(self):
        no_conformidad = self._hallazgo()
        servicios.registrar_causa_raiz(
            no_conformidad=no_conformidad, causa_raiz="Causa", usuario=self.responsable
        )
        servicios.crear_accion(
            no_conformidad=no_conformidad,
            descripcion_accion="Pendiente",
            responsable="Laura",
            fecha_limite=timezone.now().date(),
            usuario=self.responsable,
        )
        self._evidencia(no_conformidad)
        with self.assertRaises(ValidationError) as error:
            servicios.cerrar_no_conformidad(
                no_conformidad=no_conformidad, usuario=self.responsable
            )
        self.assertIn("ejecutada", " ".join(error.exception.messages))

    def test_cierre_rechaza_sin_eficacia(self):
        no_conformidad = self._hallazgo()
        servicios.registrar_causa_raiz(
            no_conformidad=no_conformidad, causa_raiz="Causa", usuario=self.responsable
        )
        accion = servicios.crear_accion(
            no_conformidad=no_conformidad,
            descripcion_accion="Ejecutada",
            responsable="Laura",
            fecha_limite=timezone.now().date(),
            usuario=self.responsable,
        )
        servicios.actualizar_accion(
            accion=accion, ejecutada=True, evaluacion_eficacia="", es_eficaz=False
        )
        self._evidencia(no_conformidad)
        with self.assertRaises(ValidationError) as error:
            servicios.cerrar_no_conformidad(
                no_conformidad=no_conformidad, usuario=self.responsable
            )
        self.assertIn("eficacia", " ".join(error.exception.messages))

    def test_cierre_rechaza_sin_evidencia(self):
        no_conformidad = self._hallazgo()
        servicios.registrar_causa_raiz(
            no_conformidad=no_conformidad, causa_raiz="Causa", usuario=self.responsable
        )
        accion = servicios.crear_accion(
            no_conformidad=no_conformidad,
            descripcion_accion="Ejecutada",
            responsable="Laura",
            fecha_limite=timezone.now().date(),
            usuario=self.responsable,
        )
        servicios.actualizar_accion(
            accion=accion, ejecutada=True, evaluacion_eficacia="Eficaz", es_eficaz=True
        )
        with self.assertRaises(ValidationError) as error:
            servicios.cerrar_no_conformidad(
                no_conformidad=no_conformidad, usuario=self.responsable
            )
        self.assertIn("evidencia", " ".join(error.exception.messages))

    def test_cierre_rechaza_si_el_archivo_no_existe(self):
        no_conformidad = self._completo()
        evidencia = no_conformidad.evidencias.first()
        evidencia.archivo.storage.delete(evidencia.archivo.name)
        with self.assertRaises(ValidationError):
            servicios.cerrar_no_conformidad(
                no_conformidad=no_conformidad, usuario=self.responsable
            )

    def test_cierre_exitoso_registra_autor_fecha_y_transicion(self):
        no_conformidad = self._completo()
        servicios.cerrar_no_conformidad(
            no_conformidad=no_conformidad, usuario=self.responsable
        )
        no_conformidad.refresh_from_db()
        self.assertEqual(no_conformidad.estado, "CERRADA")
        self.assertEqual(no_conformidad.cerrada_por, self.responsable)
        self.assertIsNotNone(no_conformidad.fecha_cierre)
        self.assertEqual(no_conformidad.transiciones.last().estado_nuevo, "CERRADA")
        self.assertEqual(no_conformidad.transiciones.last().usuario, self.responsable)

    def test_cerrada_no_admite_cambios(self):
        no_conformidad = self._completo()
        servicios.cerrar_no_conformidad(
            no_conformidad=no_conformidad, usuario=self.responsable
        )
        with self.assertRaises(ValidationError):
            servicios.registrar_causa_raiz(
                no_conformidad=no_conformidad, causa_raiz="Otra", usuario=self.responsable
            )
        with self.assertRaises(ValidationError):
            self._evidencia(no_conformidad)

    def test_evidencia_rechaza_extension(self):
        no_conformidad = self._hallazgo()
        with self.assertRaises(ValidationError):
            self._evidencia(no_conformidad, nombre="acta.exe", contenido=b"MZ...")


    def test_evidencia_rechaza_firma(self):
        no_conformidad = self._hallazgo()
        with self.assertRaises(ValidationError):
            self._evidencia(no_conformidad, contenido=b"contenido falso")

    def test_evidencia_rechaza_tamano(self):
        no_conformidad = self._hallazgo()
        grande = PDF + b"0" * (5 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            self._evidencia(no_conformidad, contenido=grande)

    def test_evidencia_queda_fuera_del_repositorio(self):
        no_conformidad = self._hallazgo()
        evidencia = self._evidencia(no_conformidad)
        ruta = Path(evidencia.archivo.path)
        self.assertTrue(ruta.is_file())
        self.assertTrue(str(ruta).startswith(str(DIR_EVIDENCIAS)))
        self.assertEqual(len(evidencia.huella), 64)
        self.assertNotIn("acta", ruta.name)

    def test_marcar_revision_respeta_accion_ejecutada(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=9,
            valor_medido="8900.00",
            evidencia="Factura EE-2026-09",
        )
        no_conformidad = NoConformidad.objects.get(medicion=medicion)
        accion = servicios.crear_accion(
            no_conformidad=no_conformidad,
            descripcion_accion="Revisar consumo",
            responsable="Laura",
            fecha_limite=timezone.now().date(),
            usuario=self.responsable,
        )
        servicios.actualizar_accion(
            accion=accion, ejecutada=True, evaluacion_eficacia="Eficaz", es_eficaz=True
        )
        servicios.marcar_revision(medicion)
        no_conformidad.refresh_from_db()
        self.assertFalse(no_conformidad.requiere_revision)

    def test_vista_lista_solo_para_responsable(self):
        self.assertEqual(self.cliente.get(reverse("gestion:lista")).status_code, 200)
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        self.assertEqual(operador.get(reverse("gestion:lista")).status_code, 403)
        self.assertEqual(Client().get(reverse("gestion:lista")).status_code, 302)

    def test_vista_nueva_crea_el_hallazgo(self):
        respuesta = self.cliente.post(
            reverse("gestion:nueva"),
            {"origen": "MANUAL", "descripcion": "Hallazgo manual", "severidad": "Alta"},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(NoConformidad.objects.filter(descripcion="Hallazgo manual").exists())

    def test_vista_nueva_no_admite_origen_automatica(self):
        respuesta = self.cliente.post(
            reverse("gestion:nueva"),
            {"origen": "AUTOMATICA", "descripcion": "Hallazgo", "severidad": "Alta"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(NoConformidad.objects.exists())

    def test_vista_causa_raiz(self):
        no_conformidad = self._hallazgo()
        respuesta = self.cliente.post(
            reverse("gestion:causa_raiz", args=[no_conformidad.pk]),
            {"causa_raiz": "Causa documentada"},
        )
        self.assertEqual(respuesta.status_code, 302)
        no_conformidad.refresh_from_db()
        self.assertEqual(no_conformidad.estado, "EN_ANALISIS")

    def test_vista_cierre_rechazado_muestra_motivos(self):
        no_conformidad = self._hallazgo()
        respuesta = self.cliente.post(
            reverse("gestion:cerrar", args=[no_conformidad.pk]), follow=True
        )
        self.assertContains(respuesta, "Registre la causa raíz del hallazgo.")
        self.assertContains(respuesta, "Adjunte una evidencia localizable")
        no_conformidad.refresh_from_db()
        self.assertEqual(no_conformidad.estado, "ABIERTA")

    def test_vista_cierre_exitoso(self):
        no_conformidad = self._completo()
        respuesta = self.cliente.post(
            reverse("gestion:cerrar", args=[no_conformidad.pk]), follow=True
        )
        self.assertContains(respuesta, "cerrada.")
        no_conformidad.refresh_from_db()
        self.assertEqual(no_conformidad.estado, "CERRADA")

    def test_descarga_exige_permiso_y_archivo_existente(self):
        no_conformidad = self._completo()
        evidencia = no_conformidad.evidencias.first()
        url = reverse(
            "gestion:descargar_evidencia", args=[no_conformidad.pk, evidencia.pk]
        )
        respuesta = self.cliente.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("attachment", respuesta["Content-Disposition"])
        respuesta.close()
        evidencia.archivo.storage.delete(evidencia.archivo.name)
        self.assertEqual(self.cliente.get(url).status_code, 404)
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        self.assertEqual(operador.get(url).status_code, 403)

    def test_operador_no_puede_cerrar_por_post_directo(self):
        no_conformidad = self._completo()
        estado_antes = no_conformidad.estado
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        respuesta = operador.post(reverse("gestion:cerrar", args=[no_conformidad.pk]))
        self.assertEqual(respuesta.status_code, 403)
        no_conformidad.refresh_from_db()
        self.assertEqual(no_conformidad.estado, estado_antes)

    def test_peticion_de_evidencia_demasiado_grande_se_rechaza(self):
        no_conformidad = self._hallazgo()
        respuesta = self.cliente.post(
            reverse("gestion:nueva_evidencia", args=[no_conformidad.pk]),
            data=None,
            CONTENT_LENGTH=str(7 * 1024 * 1024),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(EvidenciaNoConformidad.objects.exists())

    def test_operador_no_puede_adjuntar_evidencia(self):
        no_conformidad = self._hallazgo()
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        respuesta = operador.post(
            reverse("gestion:nueva_evidencia", args=[no_conformidad.pk]),
            {"archivo": SimpleUploadedFile("acta.pdf", PDF), "referencia": "Acta"},
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(EvidenciaNoConformidad.objects.exists())


@override_settings(EVIDENCIAS_RUTA=str(DIR_EVIDENCIAS))
class InmutabilidadPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.datos = preparar_catalogo()

    def test_medicion_no_se_elimina(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=8,
            valor_medido="8000.00",
            evidencia="Factura EE-2026-08",
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Medicion.objects.filter(pk=medicion.pk).delete()
        self.assertTrue(Medicion.objects.filter(pk=medicion.pk).exists())

    def test_bitacora_no_se_actualiza(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=8,
            valor_medido="8000.00",
            evidencia="Factura EE-2026-08",
        )
        operacion_servicios.editar_medicion(
            medicion=medicion,
            usuario=self.responsable,
            valor_medido="8100.00",
            evidencia="Factura EE-2026-08 corregida",
        )
        auditoria = AuditoriaMedicion.objects.get(medicion=medicion)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                AuditoriaMedicion.objects.filter(pk=auditoria.pk).update(
                    valor_nuevo=Decimal("1.00")
                )

    def test_bitacora_no_se_borra(self):
        medicion = operacion_servicios.registrar_medicion(
            usuario=self.responsable,
            indicador=self.datos["energia"],
            anio=ANIO,
            mes=8,
            valor_medido="8000.00",
            evidencia="Factura EE-2026-08",
        )
        operacion_servicios.editar_medicion(
            medicion=medicion,
            usuario=self.responsable,
            valor_medido="8100.00",
            evidencia="Factura EE-2026-08 corregida",
        )
        auditoria = AuditoriaMedicion.objects.get(medicion=medicion)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                AuditoriaMedicion.objects.filter(pk=auditoria.pk).delete()
