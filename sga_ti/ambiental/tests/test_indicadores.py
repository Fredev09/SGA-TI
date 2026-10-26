from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from ambiental.models import AspectoAmbiental, Indicador, MetaAmbiental, Proceso
from ambiental import servicios


def crear_proceso(codigo="PR-01"):
    return Proceso.objects.create(codigo=codigo, nombre="Proceso " + codigo, responsable="Responsable")


def crear_aspecto(proceso, codigo="ASP-01"):
    return AspectoAmbiental.objects.create(
        proceso=proceso,
        codigo=codigo,
        nombre="Aspecto " + codigo,
        impacto_asociado="Impacto asociado",
        es_significativo=True,
        criterio_significancia="Criterio de significancia",
    )


class CrearIndicadorPruebas(TestCase):
    def setUp(self):
        self.proceso = crear_proceso()
        self.aspecto = crear_aspecto(self.proceso)

    def test_crear_indicador_valido(self):
        indicador = servicios.crear_indicador(
            aspecto=self.aspecto,
            codigo="IND-ENE-01",
            nombre="Consumo de energía eléctrica",
            unidad_medida="kWh",
            periodicidad="Mensual",
        )
        self.assertEqual(indicador.codigo, "IND-ENE-01")
        self.assertEqual(indicador.unidad_medida, "kWh")
        self.assertEqual(indicador.periodicidad, "Mensual")
        self.assertEqual(indicador.aspecto, self.aspecto)

    def test_espacios_recortados(self):
        indicador = servicios.crear_indicador(
            aspecto=self.aspecto,
            codigo=" IND-01 ",
            nombre=" Indicador ",
            unidad_medida=" m3 ",
            periodicidad=" Mensual ",
        )
        self.assertEqual(indicador.codigo, "IND-01")
        self.assertEqual(indicador.nombre, "Indicador")
        self.assertEqual(indicador.unidad_medida, "m3")

    def test_codigo_duplicado_rechazado(self):
        servicios.crear_indicador(
            aspecto=self.aspecto, codigo="IND-01", nombre="A", unidad_medida="kWh", periodicidad="Mensual"
        )
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_indicador(
                aspecto=self.aspecto, codigo="IND-01", nombre="B", unidad_medida="kWh", periodicidad="Mensual"
            )
        self.assertIn("Ya existe un indicador con el código IND-01.", contexto.exception.messages)

    def test_aspecto_invalido_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_indicador(
                aspecto="no-es-aspecto", codigo="IND-01", nombre="A", unidad_medida="kWh", periodicidad="Mensual"
            )
        self.assertIn("El aspecto indicado no existe.", contexto.exception.messages)

    def test_campos_vacios_rechazados(self):
        casos = [
            ({"codigo": "   "}, "Ingrese el código del indicador."),
            ({"nombre": "   "}, "Ingrese el nombre del indicador."),
            ({"unidad_medida": "   "}, "Ingrese la unidad de medida del indicador."),
            ({"periodicidad": "   "}, "Ingrese la periodicidad del indicador."),
        ]
        for campos, mensaje in casos:
            datos = {
                "aspecto": self.aspecto,
                "codigo": "IND-01",
                "nombre": "Indicador",
                "unidad_medida": "kWh",
                "periodicidad": "Mensual",
            }
            datos.update(campos)
            with self.assertRaises(ValidationError) as contexto:
                servicios.crear_indicador(**datos)
            self.assertIn(mensaje, contexto.exception.messages, mensaje)

    def test_rechazo_no_deja_indicador_sin_guardar(self):
        with self.assertRaises(ValidationError):
            servicios.crear_indicador(
                aspecto=self.aspecto, codigo="   ", nombre="A", unidad_medida="kWh", periodicidad="Mensual"
            )
        self.assertFalse(Indicador.objects.exists())


class NormalizarAnioPruebas(TestCase):
    def test_sin_valor_devuelve_anio_actual(self):
        self.assertEqual(servicios.normalizar_anio(None), timezone.now().year)

    def test_anio_valido_se_respeta(self):
        self.assertEqual(servicios.normalizar_anio("2026"), 2026)
        self.assertEqual(servicios.normalizar_anio(2025), 2025)

    def test_anio_no_numerico_devuelve_actual(self):
        self.assertEqual(servicios.normalizar_anio("abc"), timezone.now().year)

    def test_anio_fuera_de_rango_devuelve_actual(self):
        self.assertEqual(servicios.normalizar_anio("999999"), timezone.now().year)
        self.assertEqual(servicios.normalizar_anio("500"), timezone.now().year)


class CatalogoIndicadoresPruebas(TestCase):
    def setUp(self):
        proceso = crear_proceso()
        aspecto = crear_aspecto(proceso)
        self.indicador_con_meta = Indicador.objects.create(
            aspecto=aspecto, codigo="IND-01", nombre="Uno", unidad_medida="kWh", periodicidad="Mensual"
        )
        MetaAmbiental.objects.create(
            indicador=self.indicador_con_meta,
            anio_vigencia=2026,
            valor_limite=Decimal("8500.00"),
            operador="<=",
            umbral_advertencia_pct=90,
        )
        self.indicador_sin_meta = Indicador.objects.create(
            aspecto=aspecto, codigo="IND-02", nombre="Dos", unidad_medida="m3", periodicidad="Mensual"
        )

    def test_catalogo_trae_solo_la_meta_del_anio(self):
        lista = list(servicios.indicadores_del_catalogo(2026))
        self.assertEqual([i.codigo for i in lista], ["IND-01", "IND-02"])
        con_meta = next(i for i in lista if i.codigo == "IND-01")
        self.assertEqual(len(con_meta.metas_anio), 1)
        self.assertEqual(con_meta.metas_anio[0].valor_limite, Decimal("8500.00"))
        sin_meta = next(i for i in lista if i.codigo == "IND-02")
        self.assertEqual(sin_meta.metas_anio, [])

    def test_catalogo_en_anio_sin_meta_lo_deja_vacio(self):
        lista = {i.codigo: i for i in servicios.indicadores_del_catalogo(2027)}
        self.assertEqual(lista["IND-01"].metas_anio, [])

    def test_sin_meta_excluye_al_que_si_tiene(self):
        sin_meta = list(servicios.indicadores_sin_meta(2026))
        self.assertEqual([i.codigo for i in sin_meta], ["IND-02"])

    def test_sin_meta_incluye_al_que_tiene_en_otro_anio(self):
        sin_meta = list(servicios.indicadores_sin_meta(2027))
        self.assertEqual(sorted(i.codigo for i in sin_meta), ["IND-01", "IND-02"])
