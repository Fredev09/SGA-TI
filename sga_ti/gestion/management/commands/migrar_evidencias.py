import hashlib
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from gestion.models import ArchivoEvidencia, EvidenciaNoConformidad


class Command(BaseCommand):
    help = "Copia a la base las evidencias que todavía están en disco."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Informa lo que haría sin guardar cambios.",
        )

    def handle(self, *args, **opciones):
        carpeta = Path(settings.EVIDENCIAS_RUTA)
        migradas = 0
        existentes = 0
        faltantes = 0
        alteradas = 0
        for evidencia in EvidenciaNoConformidad.objects.all().iterator():
            nombre = evidencia.archivo.name
            if not nombre:
                continue
            if ArchivoEvidencia.objects.filter(nombre=nombre).exists():
                existentes += 1
                continue
            origen = carpeta / nombre
            if not origen.is_file():
                faltantes += 1
                self.stderr.write("No se encontró el archivo %s" % origen)
                continue
            contenido = origen.read_bytes()
            if hashlib.sha256(contenido).hexdigest() != evidencia.huella:
                alteradas += 1
                self.stderr.write("La huella no coincide para %s" % origen)
                continue
            if not opciones["dry_run"]:
                ArchivoEvidencia.objects.create(
                    nombre=nombre, contenido=contenido, tamano=len(contenido)
                )
            migradas += 1
        if opciones["dry_run"]:
            self.stdout.write(
                "Simulación sin cambios. Se migrarían: %d" % migradas
            )
            return
        self.stdout.write(
            "Migradas: %d · ya estaban: %d · faltantes: %d · alteradas: %d"
            % (migradas, existentes, faltantes, alteradas)
        )
