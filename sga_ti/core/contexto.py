from django.conf import settings
from pathlib import Path


def estado_base_datos(request):
    return {"base_en_nube": bool(getattr(settings, "URL_BASE_DATOS", ""))}


def version_estaticos(request):
    marcas = []
    for relativa in ("static/css/base.css", "static/js/preferencias.js"):
        try:
            marcas.append(int((Path(settings.BASE_DIR) / relativa).stat().st_mtime))
        except OSError:
            marcas.append(0)
    return {"version_estaticos": max(marcas) if marcas else 0}
