import csv
import io
from decimal import ROUND_HALF_UP, Decimal

from django.http import HttpResponse
from django.utils.numberformat import format as formatear

from operacion import servicios as operacion_servicios
from operacion.models import MESES

from .models import ORIGENES, NoConformidad
from .servicios import resumen_no_conformidades

PREFIJOS_RIESGO = ("=", "+", "-", "@")


def periodo_legible(anio, mes):
    if mes:
        return "%s %s" % (dict(MESES)[mes], anio)
    return "Enero - Diciembre %s" % anio


def texto_seguro(valor):
    limpio = "" if valor is None else str(valor)
    if limpio.startswith(PREFIJOS_RIESGO):
        return "'" + limpio
    return limpio


def numero(valor):
    if valor is None:
        return ""
    return formatear(valor, ",", decimal_pos=2, use_l10n=True)


def resumen_mediciones(mediciones):
    total = len(mediciones)
    cumplidas = sum(
        1
        for medicion in mediciones
        if medicion.valor_meta is not None and medicion.valor_medido <= medicion.valor_meta
    )
    if total:
        cumplimiento = (Decimal(cumplidas) / Decimal(total) * Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        cumplimiento = Decimal("0.00")
    return {
        "total": total,
        "cumplidas": cumplidas,
        "incumplidas": total - cumplidas,
        "cumplimiento": cumplimiento,
    }


def balance_no_conformidades(anio):
    base = NoConformidad.objects.filter(fecha_deteccion__year=anio)
    balance = []
    for origen, etiqueta in ORIGENES:
        registros = base.filter(origen=origen)
        cerradas = registros.filter(estado="CERRADA").count()
        total = registros.count()
        balance.append(
            {
                "origen": etiqueta,
                "abiertas": total - cerradas,
                "cerradas": cerradas,
                "total": total,
            }
        )
    return balance


def datos_reporte(anio, mes):
    mediciones = operacion_servicios.mediciones_del_periodo(anio, mes)
    return {
        "anio": anio,
        "mes": mes,
        "periodo": periodo_legible(anio, mes),
        "mediciones": mediciones,
        "conteo": operacion_servicios.conteo_semaforo(mediciones),
        "resumen": resumen_mediciones(mediciones),
        "nc": resumen_no_conformidades(anio),
        "balance": balance_no_conformidades(anio),
    }


def construir_csv(datos):
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    resumen = datos["resumen"]
    nc = datos["nc"]

    escritor.writerow(["Reporte consolidado SGA-TI"])
    escritor.writerow(["Periodo", texto_seguro(datos["periodo"])])
    escritor.writerow(["Mediciones registradas", resumen["total"]])
    escritor.writerow(["Mediciones dentro de la meta", resumen["cumplidas"]])
    escritor.writerow(["Cumplimiento de metas (%)", numero(resumen["cumplimiento"])])
    escritor.writerow(["IRNC (%)", numero(nc["irnc"])])
    escritor.writerow(["No conformidades registradas", nc["total"]])
    escritor.writerow(["No conformidades cerradas", nc["cerradas"]])
    escritor.writerow(["No conformidades activas", nc["activas"]])
    escritor.writerow([])

    escritor.writerow(
        [
            "Indicador",
            "Codigo",
            "Unidad",
            "Anio",
            "Mes",
            "Valor medido",
            "Meta mensual",
            "Desvio (%)",
            "Estado",
            "Evidencia",
            "Registrada por",
            "Fecha de registro",
        ]
    )
    for medicion in datos["mediciones"]:
        escritor.writerow(
            [
                texto_seguro(medicion.indicador.nombre),
                texto_seguro(medicion.indicador.codigo),
                texto_seguro(medicion.indicador.unidad_medida),
                medicion.anio,
                texto_seguro(medicion.nombre_mes),
                numero(medicion.valor_medido),
                numero(medicion.valor_meta),
                numero(medicion.desvio_pct),
                texto_seguro(medicion.get_estado_semaforo_display()),
                texto_seguro(medicion.evidencia),
                texto_seguro(medicion.usuario.username),
                texto_seguro(medicion.fecha_registro.strftime("%d/%m/%Y %H:%M")),
            ]
        )
    escritor.writerow([])

    escritor.writerow(["No conformidades por origen", "Abiertas", "Cerradas", "Total"])
    for fila in datos["balance"]:
        escritor.writerow(
            [texto_seguro(fila["origen"]), fila["abiertas"], fila["cerradas"], fila["total"]]
        )
    return salida.getvalue()


def respuesta_csv(datos):
    contenido = construir_csv(datos)
    respuesta = HttpResponse(
        "\ufeff" + contenido, content_type="text/csv; charset=utf-8"
    )
    sufijo = "_%02d" % datos["mes"] if datos["mes"] else ""
    respuesta["Content-Disposition"] = (
        'attachment; filename="reporte_sga_%s%s.csv"' % (datos["anio"], sufijo)
    )
    return respuesta
