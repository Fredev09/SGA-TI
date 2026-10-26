from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from uuid import UUID

from cuentas.permisos import requiere_rol

from . import servicios
from .forms import FormularioAspecto, FormularioIndicador, FormularioMeta, FormularioProceso
from .models import Indicador


@requiere_rol("modificar_aspectos")
def catalogo(request):
    filtro = servicios.normalizar_filtro(request.GET.get("significancia"))
    contexto = {
        "procesos": servicios.procesos_del_catalogo(filtro),
        "aspectos": servicios.aspectos_del_catalogo(filtro),
        "aspectos_sin_indicador": servicios.aspectos_significativos_sin_indicador(),
        "filtro": filtro,
    }
    return render(request, "ambiental/catalogo.html", contexto)


@requiere_rol("modificar_procesos")
def proceso_nuevo(request):
    if request.method == "POST":
        formulario = FormularioProceso(request.POST)
        if formulario.is_valid():
            try:
                proceso = servicios.crear_proceso(**formulario.cleaned_data)
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(request, "Proceso %s creado." % proceso.codigo)
                return redirect("ambiental:catalogo")
    else:
        formulario = FormularioProceso()
    contexto = {
        "form": formulario,
        "titulo": "Nuevo proceso",
        "subtitulo": "RF-01 · Registro de áreas y actividades del alcance (Cláusulas 4.3 y 4.4).",
        "url_cancelar": "ambiental:catalogo",
    }
    return render(request, "ambiental/formulario.html", contexto)


@requiere_rol("modificar_aspectos")
def aspecto_nuevo(request):
    if request.method == "POST":
        formulario = FormularioAspecto(request.POST)
        if formulario.is_valid():
            try:
                aspecto = servicios.crear_aspecto(**formulario.cleaned_data)
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(request, "Aspecto %s creado." % aspecto.codigo)
                return redirect("ambiental:catalogo")
    else:
        formulario = FormularioAspecto()
    contexto = {
        "form": formulario,
        "titulo": "Nuevo aspecto ambiental",
        "subtitulo": "RF-01 · No se guarda sin impacto asociado ni dictamen de significancia.",
        "url_cancelar": "ambiental:catalogo",
    }
    return render(request, "ambiental/formulario.html", contexto)


@requiere_rol("modificar_indicadores")
def parametrizacion(request):
    anio = servicios.normalizar_anio(request.GET.get("anio"))
    contexto = {
        "indicadores": servicios.indicadores_del_catalogo(anio),
        "total_sin_meta": servicios.indicadores_sin_meta(anio).count(),
        "anio": anio,
    }
    return render(request, "ambiental/parametrizacion.html", contexto)


@requiere_rol("modificar_indicadores")
def indicador_nuevo(request):
    if request.method == "POST":
        formulario = FormularioIndicador(request.POST)
        if formulario.is_valid():
            try:
                indicador = servicios.crear_indicador(**formulario.cleaned_data)
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(request, "Indicador %s creado." % indicador.codigo)
                return redirect("ambiental:parametrizacion")
    else:
        formulario = FormularioIndicador()
    contexto = {
        "form": formulario,
        "titulo": "Nuevo indicador",
        "subtitulo": "RF-02 · Parámetro medible de seguimiento (Cláusulas 6.2 y 9.1.1).",
        "url_cancelar": "ambiental:parametrizacion",
    }
    return render(request, "ambiental/formulario.html", contexto)


@requiere_rol("modificar_metas")
def meta_nueva(request):
    inicial = {}
    if request.method == "GET":
        parametro = request.GET.get("indicador")
        if parametro:
            try:
                identificador = UUID(str(parametro))
            except (ValueError, AttributeError):
                identificador = None
            if identificador is not None and Indicador.objects.filter(pk=identificador).exists():
                inicial["indicador"] = identificador
    if request.method == "POST":
        formulario = FormularioMeta(request.POST)
        if formulario.is_valid():
            try:
                meta = servicios.crear_meta(**formulario.cleaned_data)
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(
                    request,
                    "Meta %s creada para %s." % (meta.anio_vigencia, meta.indicador.codigo),
                )
                return redirect("ambiental:parametrizacion")
    else:
        formulario = FormularioMeta(initial=inicial)
    contexto = {
        "form": formulario,
        "titulo": "Nueva meta",
        "subtitulo": "RF-02 · Límite mensual y umbral preventivo por año de vigencia (Cláusula 6.2).",
        "url_cancelar": "ambiental:parametrizacion",
    }
    return render(request, "ambiental/formulario.html", contexto)
