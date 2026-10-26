import secrets
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ambiental.models import AspectoAmbiental, Indicador, MetaAmbiental, Proceso
from cuentas.models import Usuario
from cuentas.servicios import crear_usuario
from gestion import servicios as gestion
from gestion.models import NoConformidad
from operacion import servicios as operacion
from operacion.models import MESES, Medicion

USUARIOS = (
    ("fcastro", "Freddy", "Castro", Usuario.Rol.RESPONSABLE_SGA, "fcastro@cloudtech.com.co"),
    ("keiner", "Keiner", "Ramírez", Usuario.Rol.OPERADOR, "keiner@cloudtech.com.co"),
    ("camila", "Camila", "Ruiz", Usuario.Rol.OPERADOR, "camila@cloudtech.com.co"),
    ("stiven", "Stiven", "Gómez", Usuario.Rol.OPERADOR, "stiven@cloudtech.com.co"),
    ("andres", "Andrés", "Torres", Usuario.Rol.OPERADOR, "andres@cloudtech.com.co"),
)

PROCESOS = (
    ("PR-01", "Operación de infraestructura TI", "Carlos Martínez"),
    ("PR-02", "Servicios generales y sanitarios", "Laura Gómez"),
    ("PR-03", "Gestión de activos tecnológicos", "Carlos Martínez"),
)

ASPECTOS = (
    ("ASP-01", "PR-01", "Consumo de energía eléctrica", "Agotamiento de recursos no renovables", True, "Uso de recursos no renovables por encima del umbral interno"),
    ("ASP-02", "PR-02", "Consumo de agua potable", "Presión sobre el recurso hídrico local", True, "Consumo superior al límite interno"),
    ("ASP-03", "PR-03", "Generación de residuos RAEE", "Contaminación de suelo por disposición inadecuada", True, "Generación por encima del límite mensual"),
    ("ASP-04", "PR-01", "Emisiones por planta eléctrica de emergencia", "Emisión de gases y ruido en el entorno", True, "Operación no programada con emisiones al entorno"),
    ("ASP-05", "PR-02", "Consumo de papel y suministros de oficina", "Generación de residuos sólidos", False, "Volumen dentro del rango esperado de oficina"),
    ("ASP-06", "PR-02", "Ruido por equipos de climatización", "Molestia acústica en el entorno inmediato", False, "Niveles por debajo del límite operativo interno"),
)

INDICADORES = (
    ("IND-ENE-01", "ASP-01", "Energía eléctrica", "kWh", "Factura de energía"),
    ("IND-AGU-02", "ASP-02", "Agua potable", "m3", "Recibo de acueducto"),
    ("IND-RAE-03", "ASP-03", "Residuos RAEE", "kg", "Acta de entrega de RAEE"),
)

METAS = (
    ("IND-ENE-01", "8500", 90),
    ("IND-AGU-02", "350", 90),
    ("IND-RAE-03", "100", 90),
)

VALORES = {
    "IND-ENE-01": {1: 8000, 2: 8300, 3: 8600, 4: 7800, 5: 8200, 6: 7600, 7: 8400, 8: 8100, 9: 8450, 10: 7900, 11: 8100, 12: 8000},
    "IND-AGU-02": {1: 320, 2: 330, 3: 340, 4: 300, 5: 335, 6: 310, 7: 330, 8: 345, 9: 310, 10: 325, 11: 330, 12: 320},
    "IND-RAE-03": {1: 85, 2: 92, 3: 95, 4: 80, 5: 88, 6: 90, 7: 95, 8: 92, 9: 85, 10: 88, 11: 90, 12: 85},
}


class Command(BaseCommand):
    help = "Carga datos simulados de demostración para el año indicado."

    def add_arguments(self, parser):
        parser.add_argument("--anio", type=int, default=timezone.now().year)
        parser.add_argument("--hasta", type=int, default=10)

    def handle(self, *args, **opciones):
        anio = opciones["anio"]
        hasta = opciones["hasta"]
        if not 1 <= hasta <= 12:
            raise CommandError("El mes final debe estar entre 1 y 12.")

        credenciales = []
        with transaction.atomic():
            usuarios = {}
            for username, nombre, apellido, rol, correo in USUARIOS:
                if Usuario.objects.filter(username=username).exists():
                    usuarios[username] = Usuario.objects.get(username=username)
                else:
                    clave = secrets.token_urlsafe(14)
                    usuarios[username] = crear_usuario(
                        username=username,
                        password=clave,
                        rol=rol,
                        first_name=nombre,
                        last_name=apellido,
                        email=correo,
                    )
                    credenciales.append((username, clave))

            procesos = {}
            for codigo, nombre, responsable in PROCESOS:
                procesos[codigo], _ = Proceso.objects.get_or_create(
                    codigo=codigo,
                    defaults={"nombre": nombre, "responsable": responsable},
                )

            aspectos = {}
            for codigo, proceso_codigo, nombre, impacto, significativo, criterio in ASPECTOS:
                aspectos[codigo], _ = AspectoAmbiental.objects.get_or_create(
                    codigo=codigo,
                    defaults={
                        "proceso": procesos[proceso_codigo],
                        "nombre": nombre,
                        "impacto_asociado": impacto,
                        "es_significativo": significativo,
                        "criterio_significancia": criterio,
                    },
                )

            indicadores = {}
            for codigo, aspecto_codigo, nombre, unidad, _ in INDICADORES:
                indicadores[codigo], _ = Indicador.objects.get_or_create(
                    codigo=codigo,
                    defaults={
                        "aspecto": aspectos[aspecto_codigo],
                        "nombre": nombre,
                        "unidad_medida": unidad,
                        "periodicidad": "Mensual",
                    },
                )

            for codigo, limite, umbral in METAS:
                MetaAmbiental.objects.get_or_create(
                    indicador=indicadores[codigo],
                    anio_vigencia=anio,
                    defaults={
                        "valor_limite": Decimal(limite),
                        "operador": "<=",
                        "umbral_advertencia_pct": umbral,
                    },
                )

            operadores = [usuarios[username] for username, _, _, _, _ in USUARIOS]
            sembradas = 0
            for posicion, (codigo, _, _, _, prefijo) in enumerate(INDICADORES):
                indicador = indicadores[codigo]
                for mes in range(1, hasta + 1):
                    if Medicion.objects.filter(
                        indicador=indicador, anio=anio, mes=mes
                    ).exists():
                        continue
                    operacion.registrar_medicion(
                        usuario=operadores[(posicion + mes) % len(operadores)],
                        indicador=indicador,
                        anio=anio,
                        mes=mes,
                        valor_medido=Decimal(str(VALORES[codigo][mes])),
                        evidencia="%s %s-%02d (simulada)" % (prefijo, anio, mes),
                    )
                    sembradas += 1

            responsable = usuarios["fcastro"]
            abiertas = (
                (
                    "AUDITORIA",
                    "Registro de mantenimiento de la planta eléctrica incompleto (simulado)",
                    "Alta",
                ),
                (
                    "MANUAL",
                    "Derrame menor de tóner en la bodega de suministros (simulado)",
                    "Baja",
                ),
            )
            for origen, descripcion, severidad in abiertas:
                if not NoConformidad.objects.filter(descripcion=descripcion).exists():
                    gestion.crear_manual(
                        usuario=responsable,
                        origen=origen,
                        descripcion=descripcion,
                        severidad=severidad,
                    )

            descripcion_cierre = (
                "Evidencia de auditoría interna sin firma del responsable (simulada)"
            )
            if not NoConformidad.objects.filter(descripcion=descripcion_cierre).exists():
                cerrada = gestion.crear_manual(
                    usuario=responsable,
                    origen="AUDITORIA",
                    descripcion=descripcion_cierre,
                    severidad="Media",
                )
                gestion.registrar_causa_raiz(
                    no_conformidad=cerrada,
                    causa_raiz="Control de firmas incompleto en el procedimiento de auditoría interna.",
                    usuario=responsable,
                )
                accion = gestion.crear_accion(
                    no_conformidad=cerrada,
                    descripcion_accion="Actualizar la lista de verificación y comprobar las firmas.",
                    responsable="Laura Gómez",
                    fecha_limite=timezone.now().date(),
                    usuario=responsable,
                )
                gestion.actualizar_accion(
                    accion=accion,
                    ejecutada=True,
                    evaluacion_eficacia="Auditoría posterior con firmas completas.",
                    es_eficaz=True,
                )
                gestion.adjuntar_evidencia(
                    no_conformidad=cerrada,
                    archivo=SimpleUploadedFile(
                        "acta-auditoria-demo.pdf",
                        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n",
                        content_type="application/pdf",
                    ),
                    referencia="Acta de auditoría interna simulada %s" % anio,
                    usuario=responsable,
                )
                gestion.cerrar_no_conformidad(
                    no_conformidad=cerrada, usuario=responsable
                )

        self.stdout.write(
            self.style.SUCCESS("Datos de demostración simulados cargados.")
        )
        self.stdout.write(
            "Periodo: enero a %s de %s."
            % (dict(MESES)[hasta], anio)
        )
        self.stdout.write(
            "Usuarios demo: %d · procesos: %d · aspectos: %d · indicadores: %d · metas: %d"
            % (
                Usuario.objects.filter(username__in=[u[0] for u in USUARIOS]).count(),
                Proceso.objects.count(),
                AspectoAmbiental.objects.count(),
                Indicador.objects.count(),
                MetaAmbiental.objects.filter(anio_vigencia=anio).count(),
            )
        )
        self.stdout.write(
            "Mediciones: %d nuevas · no conformidades: %d · cerradas: %d"
            % (
                sembradas,
                NoConformidad.objects.count(),
                NoConformidad.objects.filter(estado="CERRADA").count(),
            )
        )
        if credenciales:
            self.stdout.write("Cuentas creadas con contraseña temporal:")
            for username, clave in credenciales:
                self.stdout.write("  %s / %s" % (username, clave))
            self.stdout.write(
                "Cambia esas contraseñas desde Usuarios y roles cuando termines la demostración."
            )
        else:
            self.stdout.write(
                "Las cuentas demo ya existían; no se cambiaron sus contraseñas."
            )
