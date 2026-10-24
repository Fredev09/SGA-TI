from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import ModeloVersionado


class Usuario(AbstractUser, ModeloVersionado):
    class Rol(models.TextChoices):
        OPERADOR = "OPERADOR", "Operador"
        RESPONSABLE_SGA = "RESPONSABLE_SGA", "Responsable SGA"

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.OPERADOR)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rol__in=["OPERADOR", "RESPONSABLE_SGA"]),
                name="usuario_rol_valido",
            ),
        ]

    def __str__(self):
        return "%s (%s)" % (self.username, self.rol)
