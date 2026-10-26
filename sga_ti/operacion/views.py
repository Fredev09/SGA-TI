from uuid import UUID

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ambiental.models import Indicador
from cuentas.permisos import requiere_rol

from . import servicios
from .forms import FormularioPeriodo, FormularioValor
from .models import ESTADOS_SEMAFORO, MESES, Medicion


def _reglas(meta):
    if meta is None:
        return None
    return {
        "umbral": meta.valor_activacion,
        "limite": meta.valor_limite,
        "indicador": meta.indicador,
        "anio": meta.anio_vigencia,
    }


def _renderizar(request, contexto):
    contexto.update(
        {
            "titulo": "Registrar medición",
            "subtitulo": "RF-03 · Captura y edición de mediciones con evidencia y trazabilidad (Cláusula 9.1.1).",
            "bitacora": servicios.ultimas_auditorias(),
            "mis_mediciones": servicios.mediciones_de_usuario(request.user),
        }
    )
    return render(request, "operacion/medicion_formulario.html", contexto)


def _paso_periodo(request, formulario, meta=None):
    return _renderizar(
        request,
        {"paso": 1, "form_periodo": formulario, "meta": meta, "reglas": _reglas(meta)},
    )


def _paso_valor(request, datos, formulario, meta):
    return _renderizar(
        request,
        {
            "paso": 2,
            "form_periodo": None,
            "form_valor": formulario,
            "datos": datos,
            "mes_nombre": dict(MESES)[datos["mes"]],
            "meta": meta,
            "reglas": _reglas(meta),
        },
    )


def _paso_confirmacion(request, datos, formulario, meta):
    valor = formulario.cleaned_data.get("valor_medido")
    previsualizacion = None
    if valor is not None:
        estado = servicios.clasificar_estado(valor, meta)
        previsualizacion = {
            "valor_meta": meta.valor_limite,
            "umbral": meta.valor_activacion,
            "desvio": servicios.calcular_desvio(valor, meta.valor_limite),
            "estado": estado,
            "estado_display": dict(ESTADOS_SEMAFORO)[estado],
        }
    evidencia = formulario.cleaned_data.get("evidencia")
    if evidencia is None:
        evidencia = formulario["evidencia"].value() or ""
    return _renderizar(
        request,
        {
            "paso": 3,
            "form_periodo": None,
            "form_valor": formulario,
            "datos": datos,
            "mes_nombre": dict(MESES)[datos["mes"]],
            "meta": meta,
            "reglas": _reglas(meta),
            "previsualizacion": previsualizacion,
            "valor_ingresado": valor if valor is not None else formulario["valor_medido"].value(),
            "evidencia_ingresada": evidencia,
        },
    )


def _meta_del_periodo(datos):
    return servicios.buscar_meta(datos["indicador"], datos["anio"])


def _sin_meta(request, formulario, datos):
    formulario.add_error(
        None,
        "El indicador %s no tiene meta vigente para el año %s."
        % (datos["indicador"].codigo, datos["anio"]),
    )
    return _paso_periodo(request, formulario)


@requiere_rol("registrar_medicion")
def medicion_nueva(request):
    if request.method == "POST":
        periodo = FormularioPeriodo(request.POST)
        if request.POST.get("volver") == "1":
            return _paso_periodo(request, FormularioPeriodo(initial=request.POST))
        if request.POST.get("volver") == "2":
            if not periodo.is_valid():
                return _paso_periodo(request, periodo)
            meta = _meta_del_periodo(periodo.cleaned_data)
            if meta is None:
                return _sin_meta(request, periodo, periodo.cleaned_data)
            return _paso_valor(
                request, periodo.cleaned_data, FormularioValor(initial=request.POST), meta
            )
        paso = request.POST.get("paso", "1")
        if paso == "1":
            if not periodo.is_valid():
                return _paso_periodo(request, periodo)
            meta = _meta_del_periodo(periodo.cleaned_data)
            if meta is None:
                return _sin_meta(request, periodo, periodo.cleaned_data)
            return _paso_valor(request, periodo.cleaned_data, FormularioValor(), meta)
        if not periodo.is_valid():
            return _paso_periodo(request, periodo)
        meta = _meta_del_periodo(periodo.cleaned_data)
        if meta is None:
            return _sin_meta(request, periodo, periodo.cleaned_data)
        valor = FormularioValor(request.POST)
        datos = dict(periodo.cleaned_data)
        if not valor.is_valid():
            if paso == "2":
                return _paso_valor(request, datos, valor, meta)
            return _paso_confirmacion(request, datos, valor, meta)
        datos.update(valor.cleaned_data)
        if paso == "2":
            return _paso_confirmacion(request, datos, valor, meta)
        try:
            medicion = servicios.registrar_medicion(usuario=request.user, **datos)
        except ValidationError as error:
            valor.add_error(None, error)
            return _paso_confirmacion(request, datos, valor, meta)
        messages.success(
            request,
            "Medición %s/%s de %s registrada con estado %s."
            % (
                medicion.indicador.codigo,
                medicion.nombre_mes,
                medicion.anio,
                medicion.get_estado_semaforo_display(),
            ),
        )
        return redirect("operacion:medicion_nueva")

    inicial = {}
    parametro = request.GET.get("indicador")
    if parametro:
        try:
            identificador = UUID(str(parametro))
        except (ValueError, TypeError, AttributeError):
            identificador = None
        if identificador is not None and Indicador.objects.filter(pk=identificador).exists():
            inicial["indicador"] = identificador
    inicial["anio"] = timezone.now().year
    return _paso_periodo(request, FormularioPeriodo(initial=inicial))


@requiere_rol("editar_medicion")
def medicion_editar(request, medicion_id):
    medicion = get_object_or_404(Medicion, pk=medicion_id)
    if request.method == "POST":
        formulario = FormularioValor(request.POST)
        if formulario.is_valid():
            try:
                servicios.editar_medicion(
                    medicion=medicion, usuario=request.user, **formulario.cleaned_data
                )
            except ValidationError as error:
                formulario.add_error(None, error)
            else:
                messages.success(
                    request,
                    "Medición actualizada; el cambio quedó asentado en la bitácora de auditoría.",
                )
                return redirect("core:inicio")
    else:
        formulario = FormularioValor(
            initial={"valor_medido": medicion.valor_medido, "evidencia": medicion.evidencia}
        )
    contexto = {
        "medicion": medicion,
        "form": formulario,
        "meta": servicios.buscar_meta(medicion.indicador, medicion.anio),
        "historial": medicion.auditorias.select_related("usuario"),
    }
    return render(request, "operacion/medicion_edicion.html", contexto)
