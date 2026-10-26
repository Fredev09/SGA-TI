import hashlib
from pathlib import Path

from django.core.exceptions import ValidationError

MAXIMO_BYTES = 5 * 1024 * 1024

TIPOS = {
    ".pdf": "PDF",
    ".jpg": "JPG",
    ".jpeg": "JPG",
    ".png": "PNG",
}

FIRMAS = {
    "PDF": (b"%PDF-",),
    "PNG": (b"\x89PNG\r\n\x1a\n",),
    "JPG": (b"\xff\xd8\xff",),
}


def tipo_de_archivo(nombre):
    return TIPOS.get(Path(nombre or "").suffix.lower())


def validar_evidencia(archivo):
    tipo = tipo_de_archivo(archivo.name)
    if tipo is None:
        raise ValidationError("Solo se admiten archivos PDF, JPG o PNG.")
    if archivo.size > MAXIMO_BYTES:
        raise ValidationError("El archivo supera el limite de 5 MB.")
    if archivo.size == 0:
        raise ValidationError("El archivo esta vacio.")
    inicio = archivo.read(8)
    archivo.seek(0)
    if not any(inicio.startswith(firma) for firma in FIRMAS[tipo]):
        raise ValidationError("El contenido no corresponde a un PDF, JPG o PNG valido.")
    return tipo


def huella_sha256(archivo):
    resumen = hashlib.sha256()
    for trozo in archivo.chunks():
        resumen.update(trozo)
    archivo.seek(0)
    return resumen.hexdigest()


def nombre_saneado(nombre):
    return Path(nombre or "evidencia").name[:255]
