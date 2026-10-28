import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils import timezone

from ambiental.models import Indicador
from cuentas.models import Usuario

from . import servicios
from .models import Medicion

MAXIMO_BYTES = 2 * 1024 * 1024
MAXIMO_REGISTROS = 2000


def exportar():
    mediciones = Medicion.objects.select_related("indicador", "usuario").order_by(
        "anio", "mes", "indicador__codigo"
    )
    registros = [
        {
            "indicador": medicion.indicador.codigo,
            "usuario": medicion.usuario.username,
            "anio": medicion.anio,
            "mes": medicion.mes,
            "valor": str(medicion.valor_medido),
            "evidencia": medicion.evidencia,
        }
        for medicion in mediciones
    ]
    contenido = {
        "origen": "SGA-TI",
        "generado": timezone.now().isoformat(),
        "mediciones": registros,
    }
    return json.dumps(contenido, ensure_ascii=False, indent=2)


def _entero(valor, nombre):
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValidationError("El campo %s debe ser un número entero." % nombre)


def _texto(valor, nombre):
    if not isinstance(valor, str) or not valor.strip():
        raise ValidationError("El campo %s es obligatorio." % nombre)
    return valor.strip()


def importar(texto):
    try:
        contenido = json.loads(texto)
    except json.JSONDecodeError:
        raise ValidationError("El archivo no es un JSON válido.")

    if isinstance(contenido, dict):
        registros = contenido.get("mediciones")
    elif isinstance(contenido, list):
        registros = contenido
    else:
        registros = None

    if not isinstance(registros, list):
        raise ValidationError("El archivo no contiene una lista de mediciones.")
    if len(registros) > MAXIMO_REGISTROS:
        raise ValidationError(
            "El archivo supera el máximo de %d mediciones." % MAXIMO_REGISTROS
        )

    resultado = {"importadas": 0, "omitidas": 0, "errores": []}

    for posicion, registro in enumerate(registros, start=1):
        try:
            if not isinstance(registro, dict):
                raise ValidationError("La fila no tiene el formato esperado.")
            codigo = _texto(registro.get("indicador"), "indicador")
            username = _texto(registro.get("usuario"), "usuario")
            anio = _entero(registro.get("anio"), "anio")
            mes = _entero(registro.get("mes"), "mes")
            if not 1 <= mes <= 12:
                raise ValidationError("El mes debe estar entre 1 y 12.")
            try:
                valor = Decimal(str(registro.get("valor")))
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError("El valor medido debe ser un número.")
            evidencia = _texto(registro.get("evidencia"), "evidencia")

            indicador = Indicador.objects.filter(codigo=codigo).first()
            if indicador is None:
                raise ValidationError("El indicador %s no existe en esta base." % codigo)
            usuario = Usuario.objects.filter(username=username).first()
            if usuario is None:
                raise ValidationError("El usuario %s no existe en esta base." % username)

            if Medicion.objects.filter(
                indicador=indicador, anio=anio, mes=mes
            ).exists():
                resultado["omitidas"] += 1
                continue

            servicios.registrar_medicion(
                usuario=usuario,
                indicador=indicador,
                anio=anio,
                mes=mes,
                valor_medido=valor,
                evidencia=evidencia,
            )
            resultado["importadas"] += 1
        except ValidationError as error:
            resultado["errores"].append(
                {"fila": posicion, "detalle": " ".join(error.messages)}
            )

    return resultado
