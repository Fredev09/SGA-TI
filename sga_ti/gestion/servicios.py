from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.numberformat import format as formatear

from operacion.models import MESES

from .archivos import huella_sha256, nombre_saneado, validar_evidencia
from .models import (
    SEVERIDADES,
    AccionCorrectiva,
    EvidenciaNoConformidad,
    NoConformidad,
    TransicionNoConformidad,
)

ORIGENES_MANUALES = ("AUDITORIA", "MANUAL")

REQUISITOS_CIERRE = (
    ("causa_raiz", "Registre la causa raíz del hallazgo."),
    ("accion_ejecutada", "Marque al menos una acción correctiva como ejecutada."),
    ("eficacia", "Documente una verificación de eficacia satisfactoria."),
    ("evidencia", "Adjunte una evidencia localizable en PDF, JPG o PNG."),
)


def _numero_localizado(valor):
    return formatear(valor, ",", decimal_pos=2, use_l10n=True)


def _texto_obligatorio(valor, mensaje):
    limpio = (valor or "").strip()
    if not limpio:
        raise ValidationError(mensaje)
    return limpio


def _verificar_abierta(no_conformidad):
    no_conformidad.refresh_from_db(fields=["estado"])
    if no_conformidad.estado == "CERRADA":
        raise ValidationError("La no conformidad está cerrada y no admite cambios.")


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


def registrar_transicion(*, no_conformidad, estado_nuevo, usuario, observacion=""):
    anterior = no_conformidad.estado
    no_conformidad.estado = estado_nuevo
    if estado_nuevo == "CERRADA":
        no_conformidad.fecha_cierre = timezone.now()
        no_conformidad.cerrada_por = usuario
        no_conformidad.save(update_fields=["estado", "fecha_cierre", "cerrada_por"])
    else:
        no_conformidad.save(update_fields=["estado"])
    return TransicionNoConformidad.objects.create(
        no_conformidad=no_conformidad,
        estado_anterior=anterior,
        estado_nuevo=estado_nuevo,
        usuario=usuario,
        observacion=observacion,
    )


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
        no_conformidad = NoConformidad.objects.create(
            medicion=medicion,
            origen="AUTOMATICA",
            codigo=codigo_siguiente(medicion.anio),
            fecha_deteccion=timezone.now(),
            descripcion=descripcion,
            severidad="Alta",
            estado="ABIERTA",
        )
        TransicionNoConformidad.objects.create(
            no_conformidad=no_conformidad,
            estado_anterior="",
            estado_nuevo="ABIERTA",
            usuario=medicion.usuario,
            observacion="Generación automática por alerta de semáforo",
        )
        return no_conformidad


def crear_manual(*, usuario, origen, descripcion, severidad):
    if origen not in ORIGENES_MANUALES:
        raise ValidationError("El registro manual admite origen AUDITORIA o MANUAL.")
    if severidad not in dict(SEVERIDADES):
        raise ValidationError("Seleccione una severidad válida.")
    descripcion = _texto_obligatorio(descripcion, "Describa el hallazgo.")
    ahora = timezone.now()
    with transaction.atomic():
        no_conformidad = NoConformidad.objects.create(
            origen=origen,
            codigo=codigo_siguiente(ahora.year),
            fecha_deteccion=ahora,
            descripcion=descripcion,
            severidad=severidad,
            estado="ABIERTA",
        )
        TransicionNoConformidad.objects.create(
            no_conformidad=no_conformidad,
            estado_anterior="",
            estado_nuevo="ABIERTA",
            usuario=usuario,
            observacion="Registro manual del hallazgo",
        )
        return no_conformidad


def registrar_causa_raiz(*, no_conformidad, causa_raiz, usuario):
    _verificar_abierta(no_conformidad)
    texto = _texto_obligatorio(causa_raiz, "Documente la causa raíz del hallazgo.")
    with transaction.atomic():
        no_conformidad.causa_raiz = texto
        no_conformidad.save(update_fields=["causa_raiz"])
        if no_conformidad.estado == "ABIERTA":
            registrar_transicion(
                no_conformidad=no_conformidad,
                estado_nuevo="EN_ANALISIS",
                usuario=usuario,
                observacion="Causa raíz documentada",
            )
    return no_conformidad


def crear_accion(*, no_conformidad, descripcion_accion, responsable, fecha_limite, usuario):
    _verificar_abierta(no_conformidad)
    descripcion_accion = _texto_obligatorio(descripcion_accion, "Describa la acción correctiva.")
    responsable = _texto_obligatorio(responsable, "Indique el responsable de la acción.")
    if fecha_limite is None:
        raise ValidationError("Indique la fecha límite de la acción.")
    with transaction.atomic():
        accion = AccionCorrectiva.objects.create(
            no_conformidad=no_conformidad,
            descripcion_accion=descripcion_accion,
            responsable=responsable,
            fecha_limite=fecha_limite,
        )
        if no_conformidad.estado == "ABIERTA":
            registrar_transicion(
                no_conformidad=no_conformidad,
                estado_nuevo="EN_ANALISIS",
                usuario=usuario,
                observacion="Plan de acción correctiva definido",
            )
        return accion


def actualizar_accion(*, accion, ejecutada, evaluacion_eficacia, es_eficaz):
    _verificar_abierta(accion.no_conformidad)
    evaluacion = (evaluacion_eficacia or "").strip()
    if es_eficaz and not ejecutada:
        raise ValidationError("Marque la acción como ejecutada antes de declararla eficaz.")
    if es_eficaz and not evaluacion:
        raise ValidationError("Documente la evaluación de eficacia antes de declararla satisfactoria.")
    accion.ejecutada = ejecutada
    accion.evaluacion_eficacia = evaluacion
    accion.es_eficaz = bool(es_eficaz and ejecutada)
    accion.save(update_fields=["ejecutada", "evaluacion_eficacia", "es_eficaz"])
    return accion


def adjuntar_evidencia(*, no_conformidad, archivo, referencia, usuario):
    _verificar_abierta(no_conformidad)
    referencia = _texto_obligatorio(
        referencia, "Indique la referencia documental localizable de la evidencia."
    )
    tipo = validar_evidencia(archivo)
    huella = huella_sha256(archivo)
    return EvidenciaNoConformidad.objects.create(
        no_conformidad=no_conformidad,
        archivo=archivo,
        nombre_original=nombre_saneado(archivo.name),
        tipo=tipo,
        tamano=archivo.size,
        huella=huella,
        referencia=referencia,
        usuario=usuario,
    )


def requisitos_de_cierre(no_conformidad):
    eficacia = any(
        accion.es_eficaz and (accion.evaluacion_eficacia or "").strip()
        for accion in no_conformidad.acciones.all()
    )
    evidencia = any(
        evidencia.archivo and evidencia.archivo.storage.exists(evidencia.archivo.name)
        for evidencia in no_conformidad.evidencias.all()
    )
    return {
        "causa_raiz": bool((no_conformidad.causa_raiz or "").strip()),
        "accion_ejecutada": no_conformidad.acciones.filter(ejecutada=True).exists(),
        "eficacia": eficacia,
        "evidencia": evidencia,
    }


def cerrar_no_conformidad(*, no_conformidad, usuario):
    with transaction.atomic():
        actual = NoConformidad.objects.select_for_update().get(pk=no_conformidad.pk)
        if actual.estado == "CERRADA":
            raise ValidationError("La no conformidad ya está cerrada.")
        requisitos = requisitos_de_cierre(actual)
        pendientes = [
            mensaje for clave, mensaje in REQUISITOS_CIERRE if not requisitos[clave]
        ]
        if pendientes:
            raise ValidationError(pendientes)
        registrar_transicion(
            no_conformidad=actual,
            estado_nuevo="CERRADA",
            usuario=usuario,
            observacion="Cierre validado en servidor",
        )
        return actual


def marcar_revision(medicion):
    no_conformidad = NoConformidad.objects.filter(medicion=medicion, estado="ABIERTA").first()
    if no_conformidad is None or no_conformidad.requiere_revision:
        return no_conformidad
    if no_conformidad.acciones.filter(ejecutada=True).exists():
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
