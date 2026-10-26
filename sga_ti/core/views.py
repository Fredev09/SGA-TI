from django.shortcuts import render

from cuentas.permisos import requiere_rol
from gestion import servicios as gestion_servicios
from operacion import servicios as operacion_servicios
from operacion.models import MESES


@requiere_rol("ver_dashboard")
def inicio(request):
    anio = operacion_servicios.normalizar_anio(request.GET.get("anio"))
    mes = operacion_servicios.normalizar_mes(request.GET.get("mes"))
    indicadores = operacion_servicios.indicadores_con_mediciones(anio)
    seleccion = operacion_servicios.indicador_seleccionado(indicadores, request.GET.get("indicador"))
    mediciones = operacion_servicios.mediciones_del_periodo(anio, mes)
    contexto = {
        "anio": anio,
        "mes": mes,
        "mes_nombre": dict(MESES).get(mes) if mes else None,
        "MESES": MESES,
        "mediciones": mediciones,
        "conteo": operacion_servicios.conteo_semaforo(mediciones),
        "indicadores": indicadores,
        "indicador_seleccionado": seleccion,
        "tendencia": operacion_servicios.tendencia(anio, seleccion),
        "resumen_nc": gestion_servicios.resumen_no_conformidades(anio),
        "nc_activas": gestion_servicios.no_conformidades_activas(anio),
    }
    return render(request, "core/inicio.html", contexto)
