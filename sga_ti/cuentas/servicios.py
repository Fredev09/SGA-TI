from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .models import Usuario


def crear_usuario(*, username, password, rol, first_name="", last_name="", email=""):
    usuario = Usuario(
        username=username,
        rol=rol,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    validate_password(password, usuario)
    with transaction.atomic():
        usuario.set_password(password)
        usuario.save()
    return usuario
