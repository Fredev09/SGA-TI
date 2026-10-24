import secrets
import uuid

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
