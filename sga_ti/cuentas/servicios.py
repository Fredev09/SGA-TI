from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Usuario


def crear_usuario(
    *, username, password, rol, first_name="", last_name="", email="", activo=True
):
    usuario = Usuario(
        username=username,
        rol=rol,
        first_name=first_name,
        last_name=last_name,
        email=email,
        is_active=activo,
    )
    validate_password(password, usuario)
    with transaction.atomic():
        usuario.set_password(password)
        usuario.save()
    return usuario


def actualizar_usuario(*, usuario, first_name, last_name, email, rol, activo, actor):
    if usuario.pk == actor.pk and rol != usuario.rol:
        raise ValidationError("No puede cambiar su propio rol.")
    if usuario.pk == actor.pk and not activo:
        raise ValidationError("No puede desactivar su propia cuenta.")
    with transaction.atomic():
        usuario.first_name = (first_name or "").strip()
        usuario.last_name = (last_name or "").strip()
        usuario.email = (email or "").strip()
        usuario.rol = rol
        usuario.is_active = activo
        usuario.save(
            update_fields=["first_name", "last_name", "email", "rol", "is_active"]
        )
    return usuario


def cambiar_contrasena(*, usuario, password):
    validate_password(password, usuario)
    usuario.set_password(password)
    usuario.save(update_fields=["password"])
    return usuario


def alternar_activo(*, usuario, activo, actor):
    if usuario.pk == actor.pk and not activo:
        raise ValidationError("No puede desactivar su propia cuenta.")
    usuario.is_active = activo
    usuario.save(update_fields=["is_active"])
    return usuario
