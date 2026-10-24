import secrets
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from cuentas.models import Usuario
from cuentas.servicios import crear_usuario


class ModeloUsuarioPruebas(TestCase):
    def test_pk_es_uuid_unico(self):
        clave = secrets.token_urlsafe(16)
        primero = crear_usuario(username="uno", password=clave, rol=Usuario.Rol.OPERADOR)
        segundo = crear_usuario(username="dos", password=clave, rol=Usuario.Rol.OPERADOR)
        self.assertIsInstance(primero.id, uuid.UUID)
        self.assertIsInstance(segundo.id, uuid.UUID)
        self.assertNotEqual(primero.id, segundo.id)

    def test_rol_invalido_rechazado_en_base_de_datos(self):
        clave = secrets.token_urlsafe(16)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Usuario.objects.create(username="rol-malo", password=clave, rol="SUPERVISOR")

    def test_version_increce_al_editar(self):
        clave = secrets.token_urlsafe(16)
        usuario = crear_usuario(username="versionado", password=clave, rol=Usuario.Rol.OPERADOR)
        self.assertEqual(usuario.version, 1)
        usuario.first_name = "Edicion"
        usuario.save()
        usuario.refresh_from_db()
        self.assertEqual(usuario.version, 2)

    def test_fecha_creacion_inmutable_y_actualizacion_variable(self):
        clave = secrets.token_urlsafe(16)
        usuario = crear_usuario(username="fechas", password=clave, rol=Usuario.Rol.OPERADOR)
        creacion_inicial = usuario.fecha_creacion
        actualizacion_inicial = usuario.fecha_actualizacion
        usuario.save()
        usuario.refresh_from_db()
        self.assertEqual(usuario.fecha_creacion, creacion_inicial)
        self.assertNotEqual(usuario.fecha_actualizacion, actualizacion_inicial)

    def test_password_almacenada_con_hash_irreversible(self):
        clave = secrets.token_urlsafe(16)
        usuario = crear_usuario(username="cifrado", password=clave, rol=Usuario.Rol.OPERADOR)
        self.assertTrue(usuario.password.startswith("pbkdf2_"))
        self.assertNotIn(clave, usuario.password)
        self.assertTrue(usuario.check_password(clave))

    def test_rol_por_defecto_es_operador(self):
        clave = secrets.token_urlsafe(16)
        usuario = Usuario.objects.create(username="sin-rol", password=clave)
        self.assertEqual(usuario.rol, Usuario.Rol.OPERADOR)


class ValidacionContrasenaPruebas(TestCase):
    def test_contrasena_corta_rechazada(self):
        with self.assertRaises(ValidationError):
            crear_usuario(username="corto", password="abc123", rol=Usuario.Rol.OPERADOR)

    def test_contrasena_solo_numeros_rechazada(self):
        with self.assertRaises(ValidationError):
            crear_usuario(username="numerico", password="123456789012", rol=Usuario.Rol.OPERADOR)

    def test_contrasena_comun_rechazada(self):
        with self.assertRaises(ValidationError):
            crear_usuario(username="comun", password="password123", rol=Usuario.Rol.OPERADOR)

    def test_contrasena_similar_al_nombre_rechazada(self):
        with self.assertRaises(ValidationError):
            crear_usuario(
                username="keinerloco2026", password="Keinerloco2026!", rol=Usuario.Rol.OPERADOR
            )

    def test_contrasena_fuerte_aceptada_y_guardada(self):
        clave = secrets.token_urlsafe(16)
        usuario = crear_usuario(username="fuerte", password=clave, rol=Usuario.Rol.OPERADOR)
        self.assertIsNotNone(usuario.pk)
        self.assertTrue(usuario.check_password(clave))

    def test_rechazo_no_deja_usuario_sin_guardar(self):
        with self.assertRaises(ValidationError):
            crear_usuario(username="fantasma", password="abc123", rol=Usuario.Rol.OPERADOR)
        self.assertFalse(Usuario.objects.filter(username="fantasma").exists())

    def test_configura_los_cuatro_validadores_de_django(self):
        from django.conf import settings

        nombres = [v["NAME"] for v in settings.AUTH_PASSWORD_VALIDATORS]
        self.assertIn("django.contrib.auth.password_validation.UserAttributeSimilarityValidator", nombres)
        self.assertIn("django.contrib.auth.password_validation.MinimumLengthValidator", nombres)
        self.assertIn("django.contrib.auth.password_validation.CommonPasswordValidator", nombres)
        self.assertIn("django.contrib.auth.password_validation.NumericPasswordValidator", nombres)
