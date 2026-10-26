from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from cuentas.permisos import requiere_rol
from operacion import servicios as operacion_servicios
from operacion.models import MESES

from . import reportes as reportes_servicios
from . import servicios
from .forms import (
    FormularioAccion,
    FormularioAccionEstado,
    FormularioCausaRaiz,
    FormularioEvidencia,
    FormularioNoConformidad,
)
from .models import AccionCorrectiva, EvidenciaNoConformidad, NoConformidad

TIPOS_CONTENIDO = {
    "PDF": "application/pdf",
    "JPG": "image/jpeg",
    "PNG": "image/png",
}


def _contexto_detalle(no_conformidad, form_accion_estado=None, accion_editada=None, **extra):
    acciones = []
    for accion in no_conformidad.acciones.all():
        if form_accion_estado is not None and accion.pk == accion_editada:
            formulario = form_accion_estado
        else:
            formulario = FormularioAccionEstado(
                prefix="accion-%s" % accion.pk,
                initial={
                    "ejecutada": accion.ejecutada,
                    "evaluacion_eficacia": accion.evaluacion_eficacia,
                    "es_eficaz": accion.es_eficaz,
                },
            )
        acciones.append({"accion": accion, "formulario": formulario})
    contexto = {
        "no_conformidad": no_conformidad,
        "acciones": acciones,
        "evidencias": no_conformidad.evidencias.select_related("usuario"),
        "transiciones": no_conformidad.transiciones.select_related("usuario"),
        "requisitos": servicios.requisitos_de_cierre(no_conformidad),
        "form_causa": FormularioCausaRaiz(
            initial={"causa_raiz": no_conformidad.causa_raiz}
        ),
        "form_accion": FormularioAccion(),
        "form_evidencia": FormularioEvidencia(),
    }
    contexto.update(extra)
    return contexto


def _detalle(nc_id, **extra):
    return get_object_or_404(
        NoConformidad.objects.select_related(
            "medicion", "medicion__indicador", "cerrada_por"
        ),
        pk=nc_id,
    )


@requiere_rol("gestionar_no_conformidades")
def lista(request):
    filtro = request.GET.get("estado", "activas")
    base = NoConformidad.objects.select_related(
        "medicion", "medicion__indicador", "cerrada_por"
    )
    if filtro == "cerradas":
        base = base.filter(estado="CERRADA")
    elif filtro == "todas":
        pass
    else:
        filtro = "activas"
        base = base.exclude(estado="CERRADA")
    return render(
        request,
        "gestion/lista.html",
        {
            "no_conformidades": base.order_by("-fecha_deteccion"),
            "filtro": filtro,
            "resumen": servicios.resumen_no_conformidades(timezone.now().year),
        },
    )


@requiere_rol("gestionar_no_conformidades")
def nueva(request):
    formulario = FormularioNoConformidad(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        no_conformidad = servicios.crear_manual(
            usuario=request.user, **formulario.cleaned_data
        )
        messages.success(request, "No conformidad %s registrada." % no_conformidad.codigo)
        return redirect("gestion:detalle", nc_id=no_conformidad.pk)
    return render(request, "gestion/formulario.html", {"form": formulario})


@requiere_rol("gestionar_no_conformidades")
def detalle(request, nc_id):
    return render(request, "gestion/detalle.html", _contexto_detalle(_detalle(nc_id)))


@requiere_rol("gestionar_no_conformidades")
@require_POST
def causa_raiz(request, nc_id):
    no_conformidad = _detalle(nc_id)
    formulario = FormularioCausaRaiz(request.POST)
    if not formulario.is_valid():
        return render(
            request,
            "gestion/detalle.html",
            _contexto_detalle(no_conformidad, form_causa=formulario),
        )
    try:
        servicios.registrar_causa_raiz(
            no_conformidad=no_conformidad,
            causa_raiz=formulario.cleaned_data["causa_raiz"],
            usuario=request.user,
        )
    except ValidationError as error:
        formulario.add_error(None, error)
        return render(
            request,
            "gestion/detalle.html",
            _contexto_detalle(no_conformidad, form_causa=formulario),
        )
    messages.success(request, "Causa raíz registrada.")
    return redirect("gestion:detalle", nc_id=no_conformidad.pk)


@requiere_rol("gestionar_no_conformidades")
@require_POST
def nueva_accion(request, nc_id):
    no_conformidad = _detalle(nc_id)
    formulario = FormularioAccion(request.POST)
    if not formulario.is_valid():
        return render(
            request,
            "gestion/detalle.html",
            _contexto_detalle(no_conformidad, form_accion=formulario),
        )
    try:
        servicios.crear_accion(
            no_conformidad=no_conformidad, usuario=request.user, **formulario.cleaned_data
        )
    except ValidationError as error:
        formulario.add_error(None, error)
        return render(
            request,
            "gestion/detalle.html",
            _contexto_detalle(no_conformidad, form_accion=formulario),
        )
    messages.success(request, "Acción correctiva registrada.")
    return redirect("gestion:detalle", nc_id=no_conformidad.pk)


@requiere_rol("gestionar_no_conformidades")
@require_POST
def actualizar_accion(request, nc_id, accion_id):
    no_conformidad = _detalle(nc_id)
    accion = get_object_or_404(AccionCorrectiva, pk=accion_id, no_conformidad=no_conformidad)
    formulario = FormularioAccionEstado(request.POST, prefix="accion-%s" % accion.pk)
    if not formulario.is_valid():
        return render(
            request,
            "gestion/detalle.html",
            _contexto_detalle(no_conformidad, form_accion_estado=formulario, accion_editada=accion.pk),
        )
    try:
        servicios.actualizar_accion(
            accion=accion,
            ejecutada=formulario.cleaned_data["ejecutada"],
            evaluacion_eficacia=formulario.cleaned_data["evaluacion_eficacia"],
            es_eficaz=formulario.cleaned_data["es_eficaz"],
        )
    except ValidationError as error:
        formulario.add_error(None, error)
        return render(
            request,
            "gestion/detalle.html",
            _contexto_detalle(no_conformidad, form_accion_estado=formulario, accion_editada=accion.pk),
        )
    messages.success(request, "Acción correctiva actualizada.")
    return redirect("gestion:detalle", nc_id=no_conformidad.pk)


@requiere_rol("gestionar_no_conformidades")
@require_POST
def nueva_evidencia(request, nc_id):
    no_conformidad = _detalle(nc_id)
    formulario = FormularioEvidencia(request.POST, request.FILES)
    if not formulario.is_valid():
        return render(
            request,
            "gestion/detalle.html",
            _contexto_detalle(no_conformidad, form_evidencia=formulario),
        )
    try:
        servicios.adjuntar_evidencia(
            no_conformidad=no_conformidad,
            archivo=formulario.cleaned_data["archivo"],
            referencia=formulario.cleaned_data["referencia"],
            usuario=request.user,
        )
    except ValidationError as error:
        formulario.add_error(None, error)
        return render(
            request,
            "gestion/detalle.html",
            _contexto_detalle(no_conformidad, form_evidencia=formulario),
        )
    messages.success(request, "Evidencia adjuntada.")
    return redirect("gestion:detalle", nc_id=no_conformidad.pk)


@requiere_rol("gestionar_no_conformidades")
@require_POST
def cerrar(request, nc_id):
    no_conformidad = _detalle(nc_id)
    try:
        servicios.cerrar_no_conformidad(
            no_conformidad=no_conformidad, usuario=request.user
        )
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
        return redirect("gestion:detalle", nc_id=no_conformidad.pk)
    messages.success(request, "No conformidad %s cerrada." % no_conformidad.codigo)
    return redirect("gestion:detalle", nc_id=no_conformidad.pk)


@requiere_rol("generar_reportes")
def reportes(request):
    anio = operacion_servicios.normalizar_anio(request.GET.get("anio"))
    mes = operacion_servicios.normalizar_mes(request.GET.get("mes"))
    contexto = reportes_servicios.datos_reporte(anio, mes)
    contexto["MESES"] = MESES
    return render(request, "gestion/reportes.html", contexto)


@requiere_rol("generar_reportes")
def reportes_csv(request):
    anio = operacion_servicios.normalizar_anio(request.GET.get("anio"))
    mes = operacion_servicios.normalizar_mes(request.GET.get("mes"))
    return reportes_servicios.respuesta_csv(
        reportes_servicios.datos_reporte(anio, mes)
    )


@requiere_rol("gestionar_no_conformidades")
def descargar_evidencia(request, nc_id, evidencia_id):
    evidencia = get_object_or_404(
        EvidenciaNoConformidad.objects.select_related("no_conformidad"),
        pk=evidencia_id,
        no_conformidad_id=nc_id,
    )
    if not evidencia.archivo or not evidencia.archivo.storage.exists(evidencia.archivo.name):
        raise Http404("La evidencia no está disponible.")
    return FileResponse(
        evidencia.archivo.open("rb"),
        as_attachment=True,
        filename=evidencia.nombre_original,
        content_type=TIPOS_CONTENIDO.get(evidencia.tipo, "application/octet-stream"),
    )
