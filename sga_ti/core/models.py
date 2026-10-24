import uuid as _uuid

from django.db import models


class ModeloVersionado(models.Model):
    id = models.UUIDField(primary_key=True, default=_uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(default=1, editable=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True, editable=False)
    fecha_actualizacion = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self.version += 1
            actualizables = kwargs.get("update_fields")
            if actualizables is not None:
                kwargs["update_fields"] = set(actualizables) | {"version", "fecha_actualizacion"}
        super().save(*args, **kwargs)
