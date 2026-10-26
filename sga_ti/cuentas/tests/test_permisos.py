import secrets

from django.contrib.auth.models import AnonymousUser
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from cuentas.models import Usuario
from cuentas.permisos import ACCIONES, puede, requiere_rol
from cuentas.servicios import crear_usuario


class MatrizPruebas(TestCase):
    def setUp(self):
        self.clave = secrets.token_urlsafe(16)
        self.operador = crear_usuario(username="mat-ope", password=self.clave, rol=Usuario.Rol.OPERADOR)
        self.responsable = crear_usuario(
            username="mat-res", password=self.clave, rol=Usuario.Rol.RESPONSABLE_SGA
        )

    def test_operador_tiene_dashboard_registro_y_edicion(self):
        permitidas = [accion for accion in ACCIONES if puede(self.operador, accion)]
        self.assertEqual(
            sorted(permitidas), ["editar_medicion", "registrar_medicion", "ver_dashboard"]
        )

    def test_responsable_tiene_todas_las_acciones(self):
        for accion in ACCIONES:
            self.assertTrue(puede(self.responsable, accion), accion)

    def test_anonimo_no_tiene_ninguna_accion(self):
        for accion in ACCIONES:
            self.assertFalse(puede(AnonymousUser(), accion), accion)

    def test_accion_desconocida_rechazada(self):
        self.assertFalse(puede(self.responsable, "accion_inexistente"))

    def test_matriz_sin_acciones_vacias(self):
        for accion, roles in ACCIONES.items():
            self.assertTrue(roles, accion)


@override_settings(ROOT_URLCONF="cuentas.tests.urls_prueba")
class PeticionesDirectasPruebas(TestCase):
    def setUp(self):
        self.clave = secrets.token_urlsafe(16)
        self.operador = crear_usuario(username="dir-ope", password=self.clave, rol=Usuario.Rol.OPERADOR)
        self.responsable = crear_usuario(
            username="dir-res", password=self.clave, rol=Usuario.Rol.RESPONSABLE_SGA
        )
        self.cliente = Client()

    def test_anonimo_redirige_a_login(self):
        respuesta = self.cliente.get("/zona-restringida/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.startswith(reverse("cuentas:entrada")))

    def test_operador_recibe_403_en_accion_exclusiva(self):
        self.cliente.login(username="dir-ope", password=self.clave)
        respuesta = self.cliente.get("/zona-restringida/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, "Acceso denegado", status_code=403)

    def test_responsable_accede_en_accion_exclusiva(self):
        self.cliente.login(username="dir-res", password=self.clave)
        respuesta = self.cliente.get("/zona-restringida/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "acceso concedido")

    def test_decorador_exige_accion_en_matriz(self):
        with self.assertRaises(ValueError):
            requiere_rol("accion_inexistente")


class VistaInicioPruebas(TestCase):
    def setUp(self):
        self.clave = secrets.token_urlsafe(16)

    def test_ambos_roles_alcanzan_inicio(self):
        for usuario, rol in (("ope-ini", Usuario.Rol.OPERADOR), ("res-ini", Usuario.Rol.RESPONSABLE_SGA)):
            crear_usuario(username=usuario, password=self.clave, rol=rol)
            self.client.login(username=usuario, password=self.clave)
            respuesta = self.client.get(reverse("core:inicio"))
            self.assertEqual(respuesta.status_code, 200, usuario)
            self.assertContains(respuesta, "Dashboard")
            self.client.logout()
