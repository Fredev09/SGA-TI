import os
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class AlmacenEvidencias(Storage):
    def _carpeta(self):
        return Path(settings.EVIDENCIAS_RUTA)

    def _ruta(self, nombre):
        return self._carpeta() / nombre

    def path(self, name):
        return str(self._ruta(name))

    def _open(self, name, mode="rb"):
        return File(open(self.path(name), mode))

    def _save(self, name, content):
        destino = self._ruta(name)
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "wb") as archivo:
            for trozo in content.chunks():
                archivo.write(trozo)
        return name

    def exists(self, name):
        return self._ruta(name).is_file()

    def delete(self, name):
        if self.exists(name):
            os.remove(self.path(name))

    def size(self, name):
        return self._ruta(name).stat().st_size

    def url(self, name):
        raise ValueError("Las evidencias no tienen URL publica.")

    def get_available_name(self, name, max_length=None):
        return name
