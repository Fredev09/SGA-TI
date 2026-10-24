from django.core.exceptions import ValidationError
from django.db import models, transaction

from .models import AspectoAmbiental, Proceso

FILTROS = ("todos", "significativos", "no_significativos")


def normalizar_filtro(valor):
    if valor in FILTROS:
        return valor
    return "todos"


def aspectos_significativos_sin_indicador():
    return (
        AspectoAmbiental.objects.filter(es_significativo=True, indicadores__isnull=True)
        .select_related("proceso")
        .order_by("codigo")
    )


def aspectos_del_catalogo(filtro):
    consulta = (
        AspectoAmbiental.objects.select_related("proceso")
        .prefetch_related("indicadores")
        .order_by("codigo")
    )
    if filtro == "significativos":
        consulta = consulta.filter(es_significativo=True)
    elif filtro == "no_significativos":
        consulta = consulta.filter(es_significativo=False)
    return consulta


def procesos_del_catalogo(filtro):
    consulta = (
        Proceso.objects.annotate(
            total_aspectos=models.Count("aspectos", distinct=True),
            total_significativos=models.Count(
                "aspectos",
                filter=models.Q(aspectos__es_significativo=True),
                distinct=True,
            ),
            total_no_significativos=models.Count(
                "aspectos",
                filter=models.Q(aspectos__es_significativo=False),
                distinct=True,
            ),
        )
        .order_by("codigo")
    )
    if filtro == "significativos":
        consulta = consulta.filter(total_significativos__gt=0)
    elif filtro == "no_significativos":
        consulta = consulta.filter(total_no_significativos__gt=0)
    return consulta


def crear_proceso(*, codigo, nombre, responsable):
    codigo = (codigo or "").strip()
    nombre = (nombre or "").strip()
    responsable = (responsable or "").strip()
    if not codigo:
        raise ValidationError("Ingrese el código del proceso.")
    if not nombre:
        raise ValidationError("Ingrese el nombre del proceso.")
    if not responsable:
        raise ValidationError("Ingrese el responsable del proceso.")
    if Proceso.objects.filter(codigo=codigo).exists():
        raise ValidationError("Ya existe un proceso con el código %s." % codigo)
    with transaction.atomic():
        return Proceso.objects.create(codigo=codigo, nombre=nombre, responsable=responsable)


def crear_aspecto(*, proceso, codigo, nombre, impacto_asociado, es_significativo, criterio_significancia):
    codigo = (codigo or "").strip()
    nombre = (nombre or "").strip()
    impacto_asociado = (impacto_asociado or "").strip()
    criterio_significancia = (criterio_significancia or "").strip()
    if not isinstance(proceso, Proceso):
        raise ValidationError("El proceso indicado no existe.")
    if not codigo:
        raise ValidationError("Ingrese el código del aspecto.")
    if not nombre:
        raise ValidationError("Ingrese el nombre del aspecto.")
    if not impacto_asociado:
        raise ValidationError("El aspecto requiere un impacto asociado.")
    if not isinstance(es_significativo, bool):
        raise ValidationError("El aspecto requiere un dictamen de significancia.")
    if not criterio_significancia:
        raise ValidationError("El aspecto requiere un criterio de significancia.")
    if AspectoAmbiental.objects.filter(codigo=codigo).exists():
        raise ValidationError("Ya existe un aspecto con el código %s." % codigo)
    with transaction.atomic():
        return AspectoAmbiental.objects.create(
            proceso=proceso,
            codigo=codigo,
            nombre=nombre,
            impacto_asociado=impacto_asociado,
            es_significativo=es_significativo,
            criterio_significancia=criterio_significancia,
        )
