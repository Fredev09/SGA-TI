from django.db import transaction

from .models import Usuario


def crear_usuario(*, username, password, rol, first_name="", last_name="", email=""):
    with transaction.atomic():
        usuario = Usuario(
            username=username,
            rol=rol,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        usuario.set_password(password)
        usuario.save()
    return usuario
