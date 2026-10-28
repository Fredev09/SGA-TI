from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from ambiental.models import AspectoAmbiental, Indicador, MetaAmbiental, Proceso
from cuentas.models import Usuario
from gestion.models import NoConformidad
from operacion.models import Medicion


class SembrarDemoPruebas(TestCase):
    def _sembrar(self, **opciones):
        salida = StringIO()
        call_command("sembrar_demo", stdout=salida, **opciones)
        return salida.getvalue()

    def test_siembra_el_conjunto_de_demostracion(self):
        salida = self._sembrar()
        self.assertIn("simulados", salida)
        self.assertEqual(Usuario.objects.count(), 5)
        self.assertEqual(
            Usuario.objects.filter(rol=Usuario.Rol.RESPONSABLE_SGA).count(), 1
        )
        self.assertEqual(Usuario.objects.filter(rol=Usuario.Rol.OPERADOR).count(), 4)
        self.assertEqual(Proceso.objects.count(), 3)
        self.assertEqual(AspectoAmbiental.objects.count(), 6)
        self.assertEqual(Indicador.objects.count(), 3)
        self.assertEqual(MetaAmbiental.objects.count(), 3)
        self.assertEqual(Medicion.objects.count(), 30)
        self.assertFalse(Medicion.objects.filter(mes__in=(11, 12)).exists())
        self.assertEqual(NoConformidad.objects.count(), 4)
        self.assertEqual(NoConformidad.objects.filter(estado="CERRADA").count(), 1)
        self.assertEqual(
            set(NoConformidad.objects.values_list("origen", flat=True)),
            {"AUTOMATICA", "AUDITORIA", "MANUAL"},
        )
        self.assertTrue(
            NoConformidad.objects.filter(descripcion__contains="(simulad").exists()
        )
        self.assertTrue(
            NoConformidad.objects.filter(estado="CERRADA", evidencias__isnull=False).exists()
        )

    def test_no_duplica_al_ejecutar_dos_veces(self):
        self._sembrar()
        self._sembrar()
        self.assertEqual(Usuario.objects.count(), 5)
        self.assertEqual(Proceso.objects.count(), 3)
        self.assertEqual(AspectoAmbiental.objects.count(), 6)
        self.assertEqual(Indicador.objects.count(), 3)
        self.assertEqual(MetaAmbiental.objects.count(), 3)
        self.assertEqual(Medicion.objects.count(), 30)
        self.assertEqual(NoConformidad.objects.count(), 4)

    def test_respeta_el_mes_final(self):
        self._sembrar(hasta=3)
        self.assertEqual(Medicion.objects.count(), 9)
        self.assertTrue(Medicion.objects.filter(mes=3).exists())
        self.assertFalse(Medicion.objects.filter(mes=4).exists())

    def test_rechaza_mes_invalido(self):
        with self.assertRaises(Exception):
            self._sembrar(hasta=13)
