import secrets
from decimal import Decimal

from django.utils import timezone

from ambiental.models import AspectoAmbiental, Indicador, MetaAmbiental, Proceso
from cuentas.models import Usuario
from cuentas.servicios import crear_usuario

ANIO = timezone.now().year


def crear_usuarios():
    clave = secrets.token_urlsafe(16)
    operador = crear_usuario(username="keiner", password=clave, rol=Usuario.Rol.OPERADOR)
    responsable = crear_usuario(
        username="fcastro", password=clave, rol=Usuario.Rol.RESPONSABLE_SGA
    )
    return clave, operador, responsable


def preparar_catalogo(anio=ANIO):
    proceso = Proceso.objects.create(
        codigo="PR-01", nombre="Operación TI", responsable="Carlos Martínez"
    )
    aspecto = AspectoAmbiental.objects.create(
        proceso=proceso,
        codigo="ASP-01",
        nombre="Consumo de energía eléctrica",
        impacto_asociado="Agotamiento de recursos no renovables",
        es_significativo=True,
        criterio_significancia="Uso por encima del umbral interno",
    )
    energia = Indicador.objects.create(
        aspecto=aspecto,
        codigo="IND-ENE-01",
        nombre="Consumo mensual de energía",
        unidad_medida="kWh",
        periodicidad="Mensual",
    )
    agua = Indicador.objects.create(
        aspecto=aspecto,
        codigo="IND-AGU-02",
        nombre="Consumo de agua potable",
        unidad_medida="m3",
        periodicidad="Mensual",
    )
    meta_energia = MetaAmbiental.objects.create(
        indicador=energia,
        anio_vigencia=anio,
        valor_limite=Decimal("8500.00"),
        operador="<=",
        umbral_advertencia_pct=90,
    )
    meta_agua = MetaAmbiental.objects.create(
        indicador=agua,
        anio_vigencia=anio,
        valor_limite=Decimal("350.00"),
        operador="<=",
        umbral_advertencia_pct=90,
    )
    return {
        "proceso": proceso,
        "aspecto": aspecto,
        "energia": energia,
        "agua": agua,
        "meta_energia": meta_energia,
        "meta_agua": meta_agua,
    }
