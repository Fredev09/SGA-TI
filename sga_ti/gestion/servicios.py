from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.numberformat import format as formatear

from operacion.models import MESES

from .models import NoConformidad


def _numero_localizado(valor):
    return formatear(valor, ",", decimal_pos=2, use_l10n=True)


def codigo_siguiente(anio):
    prefijo = "NC-%s-" % anio
    correlativos = []
    for codigo in NoConformidad.objects.filter(codigo__startswith=prefijo).values_list("codigo", flat=True):
        sufijo = codigo[len(prefijo) :]
        if sufijo.isdigit():
            correlativos.append(int(sufijo))
    siguiente = (max(correlativos) + 1) if correlativos else 1
    return "%s%02d" % (prefijo, siguiente)


def buscar_por_medicion(medicion):
    return NoConformidad.objects.filter(medicion=medicion).first()


def crear_automatica(medicion):
    existente = buscar_por_medicion(medicion)
    if existente is not None:
        return existente
    descripcion = (
        "Medición de %s en %s de %s superó la meta mensual: %s %s frente a un máximo de %s %s."
        % (
            medicion.indicador.nombre,
            dict(MESES)[medicion.mes],
            medicion.anio,
            _numero_localizado(medicion.valor_medido),
            medicion.indicador.unidad_medida,
            _numero_localizado(medicion.valor_meta),
            medicion.indicador.unidad_medida,
        )
    )
    with transaction.atomic():
        return NoConformidad.objects.create(
            medicion=medicion,
            origen="AUTOMATICA",
            codigo=codigo_siguiente(medicion.anio),
            fecha_deteccion=timezone.now(),
            descripcion=descripcion,
            severidad="Alta",
            estado="ABIERTA",
        )


def marcar_revision(medicion):
    no_conformidad = NoConformidad.objects.filter(medicion=medicion, estado="ABIERTA").first()
    if no_conformidad is None or no_conformidad.requiere_revision:
        return no_conformidad
    no_conformidad.requiere_revision = True
    no_conformidad.save(update_fields=["requiere_revision"])
    return no_conformidad


def aplicar_reglas_de_semaforo(medicion, estado_anterior):
    if medicion.estado_semaforo == "ALERTA":
        return crear_automatica(medicion)
    if estado_anterior == "ALERTA":
        return marcar_revision(medicion)
    return None


def no_conformidades_activas(anio):
    return (
        NoConformidad.objects.filter(fecha_deteccion__year=anio)
        .exclude(estado="CERRADA")
        .select_related("medicion", "medicion__indicador")
    )


def resumen_no_conformidades(anio):
    base = NoConformidad.objects.filter(fecha_deteccion__year=anio)
    total = base.count()
    cerradas = base.filter(estado="CERRADA").count()
    if total:
        irnc = (Decimal(cerradas) / Decimal(total) * Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        irnc = Decimal("0.00")
    return {
        "total": total,
        "cerradas": cerradas,
        "abiertas": base.filter(estado="ABIERTA").count(),
        "en_analisis": base.filter(estado="EN_ANALISIS").count(),
        "activas": total - cerradas,
        "irnc": irnc,
    }
