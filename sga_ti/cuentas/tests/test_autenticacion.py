import secrets

from django.test import Client, TestCase
from django.urls import reverse

from cuentas.forms import FormularioEntrada
from cuentas.models import Usuario
from cuentas.servicios import crear_usuario


class AutenticacionPruebas(TestCase):
    def setUp(self):
        self.clave = secrets.token_urlsafe(16)
        self.operador = crear_usuario(username="keiner", password=self.clave, rol=Usuario.Rol.OPERADOR)
        self.cliente = Client()

    def test_login_correcto_redirige_a_inicio(self):
        respuesta = self.cliente.post(
            reverse("cuentas:entrada"),
            {"username": "keiner", "password": self.clave},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("core:inicio"))

    def test_login_incorrecto_muestra_error_en_espanol(self):
        respuesta = self.cliente.post(
            reverse("cuentas:entrada"),
            {"username": "keiner", "password": "clave-equivo" + secrets.token_urlsafe(8)},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Usuario o contraseña incorrectos.")

    def test_campos_vacios_muestran_error_de_servidor(self):
        respuesta = self.cliente.post(reverse("cuentas:entrada"), {})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ingrese su usuario.")
        self.assertContains(respuesta, "Ingrese su contraseña.")

    def test_inicio_anonimo_redirige_a_entrada(self):
        respuesta = self.cliente.get(reverse("core:inicio"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.startswith(reverse("cuentas:entrada")))

    def test_entrada_autenticado_redirige_a_inicio(self):
        self.cliente.login(username="keiner", password=self.clave)
        respuesta = self.cliente.get(reverse("cuentas:entrada"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("core:inicio"))

    def test_logout_por_post_cierra_sesion(self):
        self.cliente.login(username="keiner", password=self.clave)
        respuesta = self.cliente.post(reverse("cuentas:salida"))
        self.assertEqual(respuesta.status_code, 302)
        posterior = self.cliente.get(reverse("core:inicio"))
        self.assertEqual(posterior.status_code, 302)

    def test_logout_por_get_rechazado(self):
        self.cliente.login(username="keiner", password=self.clave)
        respuesta = self.cliente.get(reverse("cuentas:salida"))
        self.assertEqual(respuesta.status_code, 405)

    def test_post_sin_token_csrf_rechazado(self):
        cliente_estricto = Client(enforce_csrf_checks=True)
        respuesta = cliente_estricto.post(
            reverse("cuentas:entrada"),
            {"username": "keiner", "password": self.clave},
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_etiquetas_del_formulario_en_espanol(self):
        formulario = FormularioEntrada()
        self.assertEqual(formulario.fields["username"].label, "Usuario")
        self.assertEqual(formulario.fields["password"].label, "Contraseña")
