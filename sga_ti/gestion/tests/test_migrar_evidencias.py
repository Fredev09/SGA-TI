import hashlib
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from gestion import servicios
from gestion.models import ArchivoEvidencia, EvidenciaNoConformidad
from operacion.tests.utilidades import crear_usuarios

DIR_EVIDENCIAS = Path(tempfile.mkdtemp(prefix="sga_migracion_evidencias_"))
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n"


@override_settings(EVIDENCIAS_RUTA=str(DIR_EVIDENCIAS))
class MigrarEvidenciasPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave, cls.operador, cls.responsable = crear_usuarios()
        cls.no_conformidad = servicios.crear_manual(
            usuario=cls.responsable,
            origen="MANUAL",
            descripcion="Hallazgo para migrar evidencias",
            severidad="Media",
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(DIR_EVIDENCIAS, ignore_errors=True)

    def setUp(self):
        shutil.rmtree(DIR_EVIDENCIAS, ignore_errors=True)
        DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)

    def _evidencia(self, nombre="evidencias/legacy.pdf", huella=None):
        return EvidenciaNoConformidad.objects.create(
            no_conformidad=self.no_conformidad,
            archivo=nombre,
            nombre_original="legacy.pdf",
            tipo="PDF",
            tamano=len(PDF),
            huella=huella or hashlib.sha256(PDF).hexdigest(),
            referencia="Acta de prueba",
            usuario=self.responsable,
        )

    def _escribir(self, nombre="evidencias/legacy.pdf", contenido=PDF):
        destino = DIR_EVIDENCIAS / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)

    def _migrar(self, **opciones):
        salida = StringIO()
        errores = StringIO()
        call_command(
            "migrar_evidencias", stdout=salida, stderr=errores, **opciones
        )
        return salida.getvalue(), errores.getvalue()

    def test_migra_las_evidencias_del_disco(self):
        self._escribir()
        evidencia = self._evidencia()
        salida, _ = self._migrar()
        self.assertIn("Migradas: 1", salida)
        archivo = ArchivoEvidencia.objects.get(nombre=evidencia.archivo.name)
        self.assertEqual(bytes(archivo.contenido), PDF)
        self.assertEqual(archivo.tamano, len(PDF))

    def test_dry_run_no_guarda_cambios(self):
        self._escribir()
        self._evidencia()
        salida, _ = self._migrar(dry_run=True)
        self.assertIn("Simulación", salida)
        self.assertEqual(ArchivoEvidencia.objects.count(), 0)

    def test_es_idempotente(self):
        self._escribir()
        self._evidencia()
        self._migrar()
        salida, _ = self._migrar()
        self.assertIn("ya estaban: 1", salida)
        self.assertEqual(ArchivoEvidencia.objects.count(), 1)

    def test_informa_el_archivo_faltante(self):
        self._evidencia()
        salida, errores = self._migrar()
        self.assertIn("No se encontró", errores)
        self.assertIn("faltantes: 1", salida)
        self.assertEqual(ArchivoEvidencia.objects.count(), 0)

    def test_no_migra_si_la_huella_no_coincide(self):
        self._escribir(contenido=PDF + b"alterado")
        self._evidencia()
        salida, errores = self._migrar()
        self.assertIn("no coincide", errores)
        self.assertIn("alteradas: 1", salida)
        self.assertEqual(ArchivoEvidencia.objects.count(), 0)
