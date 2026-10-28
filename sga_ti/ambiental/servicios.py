from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from operacion import servicios as operacion_servicios
from operacion.models import AuditoriaEvaluacion, Medicion

from gestion import servicios as gestion_servicios

from .models import AspectoAmbiental, AuditoriaMeta, Indicador, MetaAmbiental, Proceso

FILTROS = ("todos", "significativos", "no_significativos")


def normalizar_anio(valor):
    anio_actual = timezone.now().year
    if valor is None:
        return anio_actual
    try:
        anio = int(valor)
    except (TypeError, ValueError):
        return anio_actual
    if not 1000 <= anio <= 9999:
        return anio_actual
    return anio


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


def indicadores_del_catalogo(anio):
    metas_del_anio = MetaAmbiental.objects.filter(anio_vigencia=anio)
    return (
        Indicador.objects.select_related("aspecto", "aspecto__proceso")
        .prefetch_related(
            models.Prefetch("metas", queryset=metas_del_anio, to_attr="metas_anio")
        )
        .order_by("codigo")
    )


def indicadores_sin_meta(anio):
    return Indicador.objects.exclude(metas__anio_vigencia=anio)


def crear_indicador(*, aspecto, codigo, nombre, unidad_medida, periodicidad):
    codigo = (codigo or "").strip()
    nombre = (nombre or "").strip()
    unidad_medida = (unidad_medida or "").strip()
    periodicidad = (periodicidad or "").strip()
    if not isinstance(aspecto, AspectoAmbiental):
        raise ValidationError("El aspecto indicado no existe.")
    if not codigo:
        raise ValidationError("Ingrese el código del indicador.")
    if not nombre:
        raise ValidationError("Ingrese el nombre del indicador.")
    if not unidad_medida:
        raise ValidationError("Ingrese la unidad de medida del indicador.")
    if not periodicidad:
        raise ValidationError("Ingrese la periodicidad del indicador.")
    if Indicador.objects.filter(codigo=codigo).exists():
        raise ValidationError("Ya existe un indicador con el código %s." % codigo)
    with transaction.atomic():
        return Indicador.objects.create(
            aspecto=aspecto,
            codigo=codigo,
            nombre=nombre,
            unidad_medida=unidad_medida,
            periodicidad=periodicidad,
        )


def crear_meta(*, indicador, anio_vigencia, valor_limite, umbral_advertencia_pct, operador="<="):
    if not isinstance(indicador, Indicador):
        raise ValidationError("El indicador indicado no existe.")
    try:
        anio = int(anio_vigencia)
    except (TypeError, ValueError):
        raise ValidationError("Ingrese el año de vigencia de la meta.")
    if anio <= 0:
        raise ValidationError("Ingrese un año de vigencia válido.")
    if valor_limite is None:
        raise ValidationError("Ingrese el límite mensual de la meta.")
    try:
        valor = Decimal(valor_limite)
    except (InvalidOperation, TypeError):
        raise ValidationError("El límite mensual debe ser un número.")
    if valor <= 0:
        raise ValidationError("El límite mensual debe ser numéricamente positivo.")
    if operador != "<=":
        raise ValidationError("Solo se admiten metas de tipo máximo permitido (<=).")
    try:
        umbral = int(umbral_advertencia_pct)
    except (TypeError, ValueError):
        raise ValidationError("Ingrese el umbral de advertencia.")
    if umbral < 50 or umbral > 99:
        raise ValidationError("El umbral de advertencia debe estar entre 50% y 99%.")
    if MetaAmbiental.objects.filter(indicador=indicador, anio_vigencia=anio).exists():
        raise ValidationError(
            "El indicador %s ya tiene una meta para el año %s." % (indicador.codigo, anio)
        )
    with transaction.atomic():
        return MetaAmbiental.objects.create(
            indicador=indicador,
            anio_vigencia=anio,
            valor_limite=valor,
            operador=operador,
            umbral_advertencia_pct=umbral,
        )


def mediciones_afectadas(meta):
    return Medicion.objects.filter(
        indicador=meta.indicador, anio=meta.anio_vigencia
    ).select_related("indicador", "usuario")


def actualizar_meta(*, meta, valor_limite, umbral_advertencia_pct, usuario):
    if not isinstance(meta, MetaAmbiental):
        raise ValidationError("La meta indicada no existe.")
    try:
        valor = Decimal(valor_limite)
    except (InvalidOperation, TypeError):
        raise ValidationError("El límite mensual debe ser un número.")
    if valor <= 0:
        raise ValidationError("El límite mensual debe ser numéricamente positivo.")
    try:
        umbral = int(umbral_advertencia_pct)
    except (TypeError, ValueError):
        raise ValidationError("Ingrese el umbral de advertencia.")
    if umbral < 50 or umbral > 99:
        raise ValidationError("El umbral de advertencia debe estar entre 50% y 99%.")

    with transaction.atomic():
        actual = MetaAmbiental.objects.select_for_update().get(pk=meta.pk)
        valor_anterior = actual.valor_limite
        umbral_anterior = actual.umbral_advertencia_pct
        actual.valor_limite = valor
        actual.umbral_advertencia_pct = umbral
        actual.save()

        mediciones = list(
            Medicion.objects.select_for_update().filter(
                indicador=actual.indicador, anio=actual.anio_vigencia
            )
        )
        for medicion in mediciones:
            estado_anterior = medicion.estado_semaforo
            meta_anterior = medicion.valor_meta
            desvio_anterior = medicion.desvio_pct
            medicion.valor_meta = actual.valor_limite
            medicion.desvio_pct = operacion_servicios.calcular_desvio(
                medicion.valor_medido, actual.valor_limite
            )
            medicion.estado_semaforo = operacion_servicios.clasificar_estado(
                medicion.valor_medido, actual
            )
            medicion.save(
                update_fields=["valor_meta", "desvio_pct", "estado_semaforo"]
            )
            AuditoriaEvaluacion.objects.create(
                medicion=medicion,
                valor_meta_anterior=meta_anterior,
                valor_meta_nuevo=medicion.valor_meta,
                desvio_anterior=desvio_anterior,
                desvio_nuevo=medicion.desvio_pct,
                estado_anterior=estado_anterior,
                estado_nuevo=medicion.estado_semaforo,
                usuario=usuario,
            )
            gestion_servicios.aplicar_reglas_de_semaforo(
                medicion, estado_anterior=estado_anterior
            )

        AuditoriaMeta.objects.create(
            meta=actual,
            valor_anterior=valor_anterior,
            valor_nuevo=actual.valor_limite,
            umbral_anterior=umbral_anterior,
            umbral_nuevo=actual.umbral_advertencia_pct,
            mediciones_recalculadas=len(mediciones),
            usuario=usuario,
        )
        return actual, len(mediciones)
