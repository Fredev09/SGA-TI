from getpass import getpass

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from cuentas.models import Usuario
from cuentas.servicios import crear_usuario


class Command(BaseCommand):
    help = "Crea un usuario de SGA-TI pidiendo la contraseña por teclado, sin valores predeterminados"

    def add_arguments(self, parser):
        parser.add_argument("usuario")
        parser.add_argument("rol", choices=["OPERADOR", "RESPONSABLE_SGA"])

    def handle(self, *args, **opciones):
        usuario = opciones["usuario"]
        rol = opciones["rol"]
        if Usuario.objects.filter(username=usuario).exists():
            raise CommandError("Ya existe un usuario con ese nombre")
        clave = getpass("Contraseña (no se muestra): ")
        confirmacion = getpass("Repita la contraseña: ")
        if not clave:
            raise CommandError("La contraseña no puede estar vacía")
        if clave != confirmacion:
            raise CommandError("Las contraseñas no coinciden")
        try:
            crear_usuario(username=usuario, password=clave, rol=rol)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages))
        self.stdout.write("Usuario %s creado con rol %s" % (usuario, rol))
