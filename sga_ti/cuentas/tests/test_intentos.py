import secrets

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from cuentas.models import Usuario
from cuentas.servicios import crear_usuario


class IntentosEntradaPruebas(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clave = secrets.token_urlsafe(16)
        cls.usuario = crear_usuario(
            username="bloqueo-uno", password=cls.clave, rol=Usuario.Rol.OPERADOR
        )
        cls.otro = crear_usuario(
            username="bloqueo-dos", password=cls.clave, rol=Usuario.Rol.OPERADOR
        )

    def setUp(self):
        cache.clear()
        self.cliente = Client()

    def tearDown(self):
        cache.clear()

    def _fallar(self, username="bloqueo-uno", password="incorrecta", ip="127.0.0.1"):
        return self.cliente.post(
            reverse("cuentas:entrada"),
            {"username": username, "password": password},
            REMOTE_ADDR=ip,
        )

    def _entrar(self, username="bloqueo-uno", ip="127.0.0.1"):
        return self.cliente.post(
            reverse("cuentas:entrada"),
            {"username": username, "password": self.clave},
            REMOTE_ADDR=ip,
        )

    def test_avisa_los_intentos_restantes(self):
        esperados = (4, 3, 2, 1)
        for restantes in esperados:
            respuesta = self._fallar()
            self.assertContains(respuesta, "Te quedan %d intento" % restantes)
            self.assertContains(respuesta, "toast-warning")

    def test_quinto_intento_bloquea_la_cuenta(self):
        for _ in range(5):
            self._fallar()
        respuesta = self._fallar()
        self.assertContains(respuesta, "Cuenta bloqueada por 15 minutos")
        respuesta = self._entrar()
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cuenta bloqueada")
        self.assertNotIn("_auth_user_id", self.cliente.session)

    def test_login_correcto_limpia_el_contador(self):
        for _ in range(3):
            self._fallar()
        self.assertEqual(self._entrar().status_code, 302)
        self.cliente.post(reverse("cuentas:salida"))
        respuesta = self._fallar()
        self.assertContains(respuesta, "Te quedan 4 intentos")

    def test_el_bloqueo_no_afecta_a_otros_usuarios(self):
        for _ in range(5):
            self._fallar()
        self.assertEqual(self._entrar(username="bloqueo-dos").status_code, 302)

    def test_el_bloqueo_es_por_ip(self):
        for _ in range(5):
            self._fallar(ip="10.0.0.1")
        self.assertEqual(self._entrar(ip="10.0.0.2").status_code, 302)

    def test_campos_vacios_no_cuentan_como_intento(self):
        for _ in range(3):
            self.cliente.post(reverse("cuentas:entrada"), {})
        respuesta = self._fallar()
        self.assertContains(respuesta, "Te quedan 4 intentos")

    def test_el_bloqueo_termina_al_expirar_el_contador(self):
        for _ in range(5):
            self._fallar()
        cache.clear()
        self.assertEqual(self._entrar().status_code, 302)

    def test_el_aviso_llega_como_notificacion_emergente(self):
        respuesta = self._fallar()
        self.assertContains(respuesta, 'class="toasts"')
        self.assertContains(respuesta, "toast toast-warning")
        self.assertContains(respuesta, "toast-cerrar")
