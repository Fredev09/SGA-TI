from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from cuentas.permisos import requiere_rol

from . import servicios
from .forms import FormularioAspecto, FormularioProceso


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
    }
    return render(request, "ambiental/formulario.html", contexto)
