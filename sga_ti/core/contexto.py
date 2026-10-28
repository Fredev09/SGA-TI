from pathlib import Path

from django.conf import settings


def version_estaticos(request):
    marcas = []
    for relativa in (
        "static/css/base.css",
        "static/js/preferencias.js",
        "static/js/avisos.js",
        "static/js/paginador.js",
    ):
        try:
            marcas.append(int((Path(settings.BASE_DIR) / relativa).stat().st_mtime))
        except OSError:
            marcas.append(0)
    return {"version_estaticos": max(marcas) if marcas else 0}
