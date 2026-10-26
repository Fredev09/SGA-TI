from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ambiental.models import Indicador, MetaAmbiental
from gestion import servicios as gestion_servicios

from .models import ESTADOS_SEMAFORO, AuditoriaMedicion, MESES, MESES_CORTOS, Medicion

ANIO_MINIMO = 1000
ANIO_MAXIMO = 9999
LONGITUD_EVIDENCIA = 250

ANCHO_GRAFICO = 680
ALTO_GRAFICO = 260
MARGEN_IZQUIERDO = 56
MARGEN_DERECHO = 16
MARGEN_SUPERIOR = 16
MARGEN_INFERIOR = 34


def normalizar_anio(valor):
    anio_actual = timezone.now().year
    if valor in (None, ""):
        return anio_actual
    try:
        anio = int(valor)
    except (TypeError, ValueError):
        return anio_actual
    if not ANIO_MINIMO <= anio <= ANIO_MAXIMO:
        return anio_actual
    return anio


def normalizar_mes(valor):
    if valor in (None, ""):
        return None
    try:
        mes = int(valor)
    except (TypeError, ValueError):
        return None
    if not 1 <= mes <= 12:
        return None
    return mes


def buscar_meta(indicador, anio):
    if not isinstance(indicador, Indicador):
        return None
    return MetaAmbiental.objects.filter(indicador=indicador, anio_vigencia=anio).first()


def clasificar_estado(valor_medido, meta):
    if valor_medido <= meta.valor_activacion:
        return "NORMAL"
    if valor_medido <= meta.valor_limite:
        return "ADVERTENCIA"
    return "ALERTA"


def calcular_desvio(valor_medido, valor_meta):
    if valor_meta is None or valor_meta <= 0:
        raise ValidationError("La meta mensual debe ser numéricamente positiva.")
    calculo = (valor_medido - valor_meta) / valor_meta * Decimal(100)
    return calculo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _validar_captura(*, indicador, anio, mes, valor_medido, evidencia):
    if not isinstance(indicador, Indicador):
        raise ValidationError("El indicador indicado no existe.")
    try:
        anio = int(anio)
    except (TypeError, ValueError):
        raise ValidationError("Ingrese un año de periodo válido.")
    if not ANIO_MINIMO <= anio <= ANIO_MAXIMO:
        raise ValidationError("Ingrese un año de periodo válido.")
    try:
        mes = int(mes)
    except (TypeError, ValueError):
        raise ValidationError("Seleccione el mes del periodo.")
    if not 1 <= mes <= 12:
        raise ValidationError("Seleccione el mes del periodo.")
    try:
        valor = Decimal(valor_medido)
    except (InvalidOperation, TypeError):
        raise ValidationError("El valor medido debe ser un número.")
    if valor < 0:
        raise ValidationError("El valor medido debe ser numérico positivo o cero.")
    evidencia = (evidencia or "").strip()
    if not evidencia:
        raise ValidationError("Ingrese la referencia de la evidencia documental de respaldo.")
    if len(evidencia) > LONGITUD_EVIDENCIA:
        raise ValidationError("La evidencia no puede superar %s caracteres." % LONGITUD_EVIDENCIA)
    meta = buscar_meta(indicador, anio)
    if meta is None:
        raise ValidationError(
            "El indicador %s no tiene meta vigente para el año %s." % (indicador.codigo, anio)
        )
    return indicador, anio, mes, valor, evidencia, meta


def registrar_medicion(*, usuario, indicador, anio, mes, valor_medido, evidencia):
    indicador, anio, mes, valor, evidencia, meta = _validar_captura(
        indicador=indicador,
        anio=anio,
        mes=mes,
        valor_medido=valor_medido,
        evidencia=evidencia,
    )
    if Medicion.objects.filter(indicador=indicador, anio=anio, mes=mes).exists():
        raise ValidationError(
            "Ya existe una medición de %s para %s de %s."
            % (indicador.codigo, dict(MESES)[mes], anio)
        )
    valor_meta = meta.valor_limite
    desvio = calcular_desvio(valor, valor_meta)
    estado = clasificar_estado(valor, meta)
    with transaction.atomic():
        medicion = Medicion.objects.create(
            indicador=indicador,
            anio=anio,
            mes=mes,
            valor_medido=valor,
            valor_meta=valor_meta,
            desvio_pct=desvio,
            estado_semaforo=estado,
            usuario=usuario,
            evidencia=evidencia,
        )
        gestion_servicios.aplicar_reglas_de_semaforo(medicion, estado_anterior=None)
        return medicion


def editar_medicion(*, medicion, usuario, valor_medido, evidencia):
    if not isinstance(medicion, Medicion):
        raise ValidationError("La medición indicada no existe.")
    indicador, anio, mes, valor, evidencia, meta = _validar_captura(
        indicador=medicion.indicador,
        anio=medicion.anio,
        mes=medicion.mes,
        valor_medido=valor_medido,
        evidencia=evidencia,
    )
    estado_anterior = medicion.estado_semaforo
    valor_anterior = medicion.valor_medido
    valor_meta = meta.valor_limite
    desvio = calcular_desvio(valor, valor_meta)
    estado = clasificar_estado(valor, meta)
    with transaction.atomic():
        medicion.valor_medido = valor
        medicion.valor_meta = valor_meta
        medicion.desvio_pct = desvio
        medicion.estado_semaforo = estado
        medicion.evidencia = evidencia
        medicion.save()
        AuditoriaMedicion.objects.create(
            medicion=medicion,
            valor_anterior=valor_anterior,
            valor_nuevo=valor,
            usuario=usuario,
        )
        gestion_servicios.aplicar_reglas_de_semaforo(medicion, estado_anterior=estado_anterior)
        return medicion


def mediciones_del_periodo(anio, mes=None):
    consulta = Medicion.objects.select_related(
        "indicador", "indicador__aspecto", "usuario"
    ).filter(anio=anio)
    if mes is not None:
        consulta = consulta.filter(mes=mes)
    return consulta.order_by("indicador__codigo", "mes")


def conteo_semaforo(mediciones):
    conteo = {"NORMAL": 0, "ADVERTENCIA": 0, "ALERTA": 0}
    for medicion in mediciones:
        if medicion.estado_semaforo in conteo:
            conteo[medicion.estado_semaforo] += 1
    return conteo


def indicadores_con_mediciones(anio):
    return (
        Indicador.objects.filter(mediciones__anio=anio)
        .distinct()
        .select_related("aspecto")
        .order_by("codigo")
    )


def indicador_seleccionado(indicadores, parametro):
    if not indicadores:
        return None
    if parametro:
        for indicador in indicadores:
            if str(indicador.pk) == str(parametro):
                return indicador
    return indicadores[0]


def ultimas_auditorias(limite=20):
    return AuditoriaMedicion.objects.select_related(
        "medicion", "medicion__indicador", "usuario"
    )[:limite]


def mediciones_de_usuario(usuario, limite=5):
    return Medicion.objects.select_related("indicador").filter(usuario=usuario)[:limite]


def _coordenada(valor):
    return "%.2f" % float(valor)


def _referencia_y(valor, base, tope):
    fraccion = (valor - base) / (tope - base)
    return MARGEN_SUPERIOR + Decimal(ALTO_GRAFICO - MARGEN_SUPERIOR - MARGEN_INFERIOR) * (
        Decimal(1) - fraccion
    )


def tendencia(anio, indicador):
    if indicador is None:
        return None
    mediciones = list(Medicion.objects.filter(anio=anio, indicador=indicador).order_by("mes"))
    if not mediciones:
        return None
    meta = buscar_meta(indicador, anio)
    referencias = [m.valor_medido for m in mediciones]
    if meta is not None:
        referencias += [meta.valor_limite, meta.valor_activacion]
    minimo = min(referencias)
    maximo = max(referencias)
    rango = maximo - minimo
    if rango <= 0:
        rango = maximo if maximo > 0 else Decimal(1)
    base = minimo - rango * Decimal("0.2")
    if base < 0:
        base = Decimal(0)
    tope = maximo + rango * Decimal("0.2")
    if tope <= base:
        tope = base + Decimal(1)

    ancho_util = Decimal(ANCHO_GRAFICO - MARGEN_IZQUIERDO - MARGEN_DERECHO)

    def coordenada_x(mes):
        return Decimal(MARGEN_IZQUIERDO) + ancho_util * Decimal(mes - 1) / Decimal(11)

    puntos = []
    for medicion in mediciones:
        puntos.append(
            {
                "x": _coordenada(coordenada_x(medicion.mes)),
                "y": _coordenada(_referencia_y(medicion.valor_medido, base, tope)),
                "valor": medicion.valor_medido,
                "nombre_mes": dict(MESES)[medicion.mes],
                "estado": medicion.estado_semaforo,
                "estado_display": dict(ESTADOS_SEMAFORO)[medicion.estado_semaforo],
            }
        )

    rejilla = []
    for indice in range(4):
        valor = base + (tope - base) * Decimal(indice) / Decimal(3)
        posicion = _referencia_y(valor, base, tope)
        rejilla.append(
            {
                "y": _coordenada(posicion),
                "etiqueta_y": _coordenada(posicion + Decimal(4)),
                "etiqueta": valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            }
        )

    eje_x = [
        {"x": _coordenada(coordenada_x(medicion.mes)), "etiqueta": MESES_CORTOS[medicion.mes - 1]}
        for medicion in mediciones
    ]

    contexto = {
        "polilinea": " ".join("%s,%s" % (punto["x"], punto["y"]) for punto in puntos),
        "puntos": puntos,
        "eje_x": eje_x,
        "rejilla": rejilla,
        "meta": None,
        "umbral": None,
        "meta_y": None,
        "umbral_y": None,
        "margen_izquierdo": MARGEN_IZQUIERDO,
        "ancho": ANCHO_GRAFICO - MARGEN_DERECHO,
        "base": _coordenada(ALTO_GRAFICO - MARGEN_INFERIOR),
    }
    if meta is not None:
        contexto["meta"] = meta.valor_limite
        contexto["umbral"] = meta.valor_activacion
        contexto["meta_y"] = _coordenada(_referencia_y(meta.valor_limite, base, tope))
        contexto["umbral_y"] = _coordenada(_referencia_y(meta.valor_activacion, base, tope))
    return contexto
