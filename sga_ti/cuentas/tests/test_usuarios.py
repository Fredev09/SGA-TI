import secrets

from django.contrib.auth import authenticate
from django.test import Client, TestCase
from django.urls import reverse

from cuentas.models import Usuario
from cuentas.servicios import crear_usuario

CLAVE_NUEVA = "Clave-Segura-2026"


class UsuariosPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        cls.operador = crear_usuario(
            username="keiner", password=cls.clave, rol=Usuario.Rol.OPERADOR
        )
        cls.responsable = crear_usuario(
            username="fcastro", password=cls.clave, rol=Usuario.Rol.RESPONSABLE_SGA
        )

    def setUp(self):
        self.cliente = Client()
        self.cliente.login(username="fcastro", password=self.clave)

    def _datos_alta(self, **extras):
        datos = {
            "username": "camila",
            "first_name": "Camila",
            "last_name": "Ruiz",
            "email": "camila@cloudtech.test",
            "rol": "OPERADOR",
            "activo": "on",
            "password1": CLAVE_NUEVA,
            "password2": CLAVE_NUEVA,
        }
        datos.update(extras)
        return datos

    def test_lista_solo_para_responsable(self):
        self.assertEqual(self.cliente.get(reverse("cuentas:usuarios")).status_code, 200)
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        self.assertEqual(operador.get(reverse("cuentas:usuarios")).status_code, 403)
        self.assertEqual(Client().get(reverse("cuentas:usuarios")).status_code, 302)

    def test_lista_muestra_cuentas_y_roles(self):
        respuesta = self.cliente.get(reverse("cuentas:usuarios"))
        self.assertContains(respuesta, "keiner")
        self.assertContains(respuesta, "Operador")
        self.assertContains(respuesta, "Responsable SGA")
        self.assertContains(respuesta, "Nuevo usuario")

    def test_nuevo_usuario_crea_cuenta_con_contrasena(self):
        respuesta = self.cliente.post(
            reverse("cuentas:usuario_nuevo"), self._datos_alta()
        )
        self.assertEqual(respuesta.status_code, 302)
        usuario = Usuario.objects.get(username="camila")
        self.assertEqual(usuario.rol, "OPERADOR")
        self.assertTrue(usuario.is_active)
        self.assertIsNotNone(authenticate(username="camila", password=CLAVE_NUEVA))

    def test_nuevo_usuario_duplicado(self):
        respuesta = self.cliente.post(
            reverse("cuentas:usuario_nuevo"), self._datos_alta(username="keiner")
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe un usuario con ese nombre.")

    def test_nuevo_usuario_contrasenas_distintas(self):
        respuesta = self.cliente.post(
            reverse("cuentas:usuario_nuevo"),
            self._datos_alta(password2="Otra-Clave-2026"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Las contraseñas no coinciden.")
        self.assertFalse(Usuario.objects.filter(username="camila").exists())

    def test_nuevo_usuario_contrasena_debil(self):
        respuesta = self.cliente.post(
            reverse("cuentas:usuario_nuevo"),
            self._datos_alta(password1="12345678", password2="12345678"),
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username="camila").exists())

    def test_editar_usuario(self):
        respuesta = self.cliente.post(
            reverse("cuentas:usuario_editar", args=[self.operador.pk]),
            {
                "first_name": "Keiner",
                "last_name": "Martínez",
                "email": "keiner@cloudtech.test",
                "rol": "RESPONSABLE_SGA",
                "activo": "on",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        self.operador.refresh_from_db()
        self.assertEqual(self.operador.first_name, "Keiner")
        self.assertEqual(self.operador.rol, "RESPONSABLE_SGA")

    def test_no_puede_cambiar_su_propio_rol(self):
        respuesta = self.cliente.post(
            reverse("cuentas:usuario_editar", args=[self.responsable.pk]),
            {
                "first_name": "",
                "last_name": "",
                "email": "",
                "rol": "OPERADOR",
                "activo": "on",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No puede cambiar su propio rol.")
        self.responsable.refresh_from_db()
        self.assertEqual(self.responsable.rol, "RESPONSABLE_SGA")

    def test_no_puede_desactivar_su_cuenta(self):
        respuesta = self.cliente.post(
            reverse("cuentas:usuario_estado", args=[self.responsable.pk]), follow=True
        )
        self.assertContains(respuesta, "No puede desactivar su propia cuenta.")
        self.responsable.refresh_from_db()
        self.assertTrue(self.responsable.is_active)

    def test_desactivar_y_activar_otra_cuenta(self):
        self.cliente.post(reverse("cuentas:usuario_estado", args=[self.operador.pk]))
        self.operador.refresh_from_db()
        self.assertFalse(self.operador.is_active)
        self.cliente.post(reverse("cuentas:usuario_estado", args=[self.operador.pk]))
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.is_active)

    def test_restablecer_contrasena(self):
        respuesta = self.cliente.post(
            reverse("cuentas:usuario_contrasena", args=[self.operador.pk]),
            {"password1": CLAVE_NUEVA, "password2": CLAVE_NUEVA},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertIsNone(authenticate(username="keiner", password=self.clave))
        self.assertIsNotNone(authenticate(username="keiner", password=CLAVE_NUEVA))

    def test_restablecer_con_contrasena_debil(self):
        respuesta = self.cliente.post(
            reverse("cuentas:usuario_contrasena", args=[self.operador.pk]),
            {"password1": "12345678", "password2": "12345678"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNotNone(authenticate(username="keiner", password=self.clave))

    def test_operador_recibe_403_en_todas_las_rutas(self):
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        rutas = [
            reverse("cuentas:usuarios"),
            reverse("cuentas:usuario_nuevo"),
            reverse("cuentas:usuario_editar", args=[self.responsable.pk]),
            reverse("cuentas:usuario_contrasena", args=[self.responsable.pk]),
        ]
        for ruta in rutas:
            self.assertEqual(operador.get(ruta).status_code, 403, ruta)
        respuesta = operador.post(
            reverse("cuentas:usuario_estado", args=[self.responsable.pk])
        )
        self.assertEqual(respuesta.status_code, 403)
        self.responsable.refresh_from_db()
        self.assertTrue(self.responsable.is_active)

    def test_post_sin_csrf_rechazado(self):
        estricto = Client(enforce_csrf_checks=True)
        estricto.login(username="fcastro", password=self.clave)
        respuesta = estricto.post(
            reverse("cuentas:usuario_estado", args=[self.operador.pk])
        )
        self.assertEqual(respuesta.status_code, 403)
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.is_active)

    def test_preferencias_disponible_para_ambos_roles(self):
        respuesta = self.cliente.get(reverse("cuentas:preferencias"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Modo claro")
        self.assertContains(respuesta, "Modo oscuro")
        self.assertContains(respuesta, "data-tema")
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        self.assertEqual(operador.get(reverse("cuentas:preferencias")).status_code, 200)
        self.assertEqual(Client().get(reverse("cuentas:preferencias")).status_code, 302)

    def test_navegacion_muestra_usuarios_solo_al_responsable(self):
        respuesta = self.cliente.get(reverse("core:inicio"))
        self.assertContains(respuesta, "Usuarios y roles")
        self.assertContains(respuesta, "Preferencias del sistema")
        operador = Client()
        operador.login(username="keiner", password=self.clave)
        respuesta_operador = operador.get(reverse("core:inicio"))
        self.assertNotContains(respuesta_operador, "Usuarios y roles")
        self.assertContains(respuesta_operador, "Preferencias del sistema")
