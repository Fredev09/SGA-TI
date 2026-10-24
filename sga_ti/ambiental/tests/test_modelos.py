from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from ambiental.models import AspectoAmbiental, Indicador, Proceso
from ambiental import servicios


def crear_proceso_base(codigo="PR-01"):
    return Proceso.objects.create(codigo=codigo, nombre="Operación de infraestructura TI", responsable="Carlos Martínez")


class ModeloProcesoPruebas(TestCase):
    def test_codigo_unico_rechaza_duplicado(self):
        Proceso.objects.create(codigo="PR-01", nombre="Proceso", responsable="Responsable")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Proceso.objects.create(codigo="PR-01", nombre="Otro", responsable="Otro")

    def test_str_muestra_codigo_y_nombre(self):
        proceso = crear_proceso_base()
        self.assertEqual(str(proceso), "PR-01 · Operación de infraestructura TI")

    def test_hereda_versionado(self):
        proceso = crear_proceso_base()
        self.assertEqual(proceso.version, 1)
        self.assertIsNotNone(proceso.fecha_creacion)
        self.assertIsNotNone(proceso.fecha_actualizacion)


class ModeloAspectoPruebas(TestCase):
    def setUp(self):
        self.proceso = crear_proceso_base()

    def crear_aspecto(self, codigo="ASP-01", significativo=True):
        return AspectoAmbiental.objects.create(
            proceso=self.proceso,
            codigo=codigo,
            nombre="Consumo de energía eléctrica",
            impacto_asociado="Agotamiento de recursos no renovables",
            es_significativo=significativo,
            criterio_significancia="Uso de recursos no renovables por encima del umbral interno",
        )

    def test_codigo_unico_rechaza_duplicado(self):
        self.crear_aspecto()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_aspecto()

    def test_es_significativo_no_admite_nulo(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AspectoAmbiental.objects.create(
                    proceso=self.proceso,
                    codigo="ASP-02",
                    nombre="Sin dictamen",
                    impacto_asociado="Impacto",
                    es_significativo=None,
                    criterio_significancia="Criterio",
                )

    def test_borrar_proceso_con_aspectos_esta_protegido(self):
        self.crear_aspecto()
        with self.assertRaises(ProtectedError):
            with transaction.atomic():
                self.proceso.delete()

    def test_relacion_inversa_con_proceso(self):
        aspecto = self.crear_aspecto()
        self.assertIn(aspecto, self.proceso.aspectos.all())


class ModeloIndicadorPruebas(TestCase):
    def test_relacion_inversa_con_aspecto(self):
        proceso = crear_proceso_base()
        aspecto = AspectoAmbiental.objects.create(
            proceso=proceso,
            codigo="ASP-01",
            nombre="Consumo de energía eléctrica",
            impacto_asociado="Agotamiento de recursos no renovables",
            es_significativo=True,
            criterio_significancia="Criterio",
        )
        indicador = Indicador.objects.create(
            aspecto=aspecto,
            codigo="IND-ENE-01",
            nombre="Consumo mensual de energía eléctrica",
            unidad_medida="kWh",
            periodicidad="Mensual",
        )
        self.assertIn(indicador, aspecto.indicadores.all())


class ServicioCrearProcesoPruebas(TestCase):
    def test_crear_proceso_valido(self):
        proceso = servicios.crear_proceso(codigo=" PR-01 ", nombre=" Proceso ", responsable=" Responsable ")
        self.assertEqual(proceso.codigo, "PR-01")
        self.assertEqual(proceso.nombre, "Proceso")
        self.assertEqual(proceso.responsable, "Responsable")

    def test_codigo_vacio_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_proceso(codigo="   ", nombre="Proceso", responsable="Responsable")
        self.assertIn("Ingrese el código del proceso.", contexto.exception.messages)

    def test_nombre_vacio_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_proceso(codigo="PR-01", nombre="", responsable="Responsable")
        self.assertIn("Ingrese el nombre del proceso.", contexto.exception.messages)

    def test_responsable_vacio_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_proceso(codigo="PR-01", nombre="Proceso", responsable="  ")
        self.assertIn("Ingrese el responsable del proceso.", contexto.exception.messages)

    def test_codigo_duplicado_rechazado(self):
        servicios.crear_proceso(codigo="PR-01", nombre="Proceso", responsable="Responsable")
        with self.assertRaises(ValidationError) as contexto:
            servicios.crear_proceso(codigo="PR-01", nombre="Otro", responsable="Otro")
        self.assertIn("Ya existe un proceso con el código PR-01.", contexto.exception.messages)


class ServicioCrearAspectoPruebas(TestCase):
    def setUp(self):
        self.proceso = crear_proceso_base()

    def crear_aspecto(self, **campos):
        datos = {
            "proceso": self.proceso,
            "codigo": "ASP-01",
            "nombre": "Consumo de energía eléctrica",
            "impacto_asociado": "Agotamiento de recursos no renovables",
            "es_significativo": True,
            "criterio_significancia": "Criterio técnico",
        }
        datos.update(campos)
        return servicios.crear_aspecto(**datos)

    def test_crear_aspecto_valido(self):
        aspecto = self.crear_aspecto()
        self.assertEqual(aspecto.codigo, "ASP-01")
        self.assertTrue(aspecto.es_significativo)
        self.assertEqual(aspecto.proceso, self.proceso)

    def test_impacto_vacio_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            self.crear_aspecto(impacto_asociado="   ")
        self.assertIn("El aspecto requiere un impacto asociado.", contexto.exception.messages)

    def test_dictamen_ausente_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            self.crear_aspecto(es_significativo=None)
        self.assertIn("El aspecto requiere un dictamen de significancia.", contexto.exception.messages)

    def test_dictamen_no_significativo_aceptado(self):
        aspecto = self.crear_aspecto(es_significativo=False)
        self.assertFalse(aspecto.es_significativo)

    def test_criterio_vacio_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            self.crear_aspecto(criterio_significancia="  ")
        self.assertIn("El aspecto requiere un criterio de significancia.", contexto.exception.messages)

    def test_proceso_invalido_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            self.crear_aspecto(proceso="no-es-proceso")
        self.assertIn("El proceso indicado no existe.", contexto.exception.messages)

    def test_codigo_duplicado_rechazado(self):
        self.crear_aspecto()
        with self.assertRaises(ValidationError) as contexto:
            self.crear_aspecto(nombre="Otro aspecto")
        self.assertIn("Ya existe un aspecto con el código ASP-01.", contexto.exception.messages)

    def test_significativo_sin_indicador_no_bloquea_insercion(self):
        aspecto = self.crear_aspecto()
        self.assertTrue(aspecto.pk is not None)


class ServicioAlertaPruebas(TestCase):
    def setUp(self):
        self.proceso = crear_proceso_base()
        self.otro_proceso = crear_proceso_base(codigo="PR-02")
        self.aspecto_significativo = self.crear_aspecto(self.proceso, "ASP-01", True)
        self.aspecto_no_significativo = self.crear_aspecto(self.proceso, "ASP-02", False)

    def crear_aspecto(self, proceso, codigo, significativo):
        return AspectoAmbiental.objects.create(
            proceso=proceso,
            codigo=codigo,
            nombre="Aspecto %s" % codigo,
            impacto_asociado="Impacto %s" % codigo,
            es_significativo=significativo,
            criterio_significancia="Criterio %s" % codigo,
        )

    def test_alerta_incluye_significativo_sin_indicador(self):
        resultado = list(servicios.aspectos_significativos_sin_indicador())
        self.assertEqual([a.codigo for a in resultado], ["ASP-01"])

    def test_alerta_excluye_significativo_con_indicador(self):
        Indicador.objects.create(
            aspecto=self.aspecto_significativo,
            codigo="IND-ENE-01",
            nombre="Indicador",
            unidad_medida="kWh",
            periodicidad="Mensual",
        )
        self.assertEqual(list(servicios.aspectos_significativos_sin_indicador()), [])

    def test_alerta_excluye_no_significativo(self):
        self.assertEqual(
            [a.codigo for a in servicios.aspectos_significativos_sin_indicador()],
            ["ASP-01"],
        )
        self.assertNotIn(self.aspecto_no_significativo, servicios.aspectos_significativos_sin_indicador())


class ServicioFiltroPruebas(TestCase):
    def test_filtro_invalido_normaliza_a_todos(self):
        self.assertEqual(servicios.normalizar_filtro(None), "todos")
        self.assertEqual(servicios.normalizar_filtro("otro"), "todos")
        self.assertEqual(servicios.normalizar_filtro("significativos"), "significativos")

    def test_listado_filtra_por_significancia(self):
        proceso = crear_proceso_base()
        for codigo, significativo in (("ASP-01", True), ("ASP-02", False), ("ASP-03", True)):
            AspectoAmbiental.objects.create(
                proceso=proceso,
                codigo=codigo,
                nombre=codigo,
                impacto_asociado=codigo,
                es_significativo=significativo,
                criterio_significancia=codigo,
            )
        significativos = list(servicios.aspectos_del_catalogo("significativos"))
        no_significativos = list(servicios.aspectos_del_catalogo("no_significativos"))
        todos = list(servicios.aspectos_del_catalogo("todos"))
        self.assertEqual([a.codigo for a in significativos], ["ASP-01", "ASP-03"])
        self.assertEqual([a.codigo for a in no_significativos], ["ASP-02"])
        self.assertEqual(len(todos), 3)

    def test_procesos_filtra_por_significancia_de_aspectos(self):
        proceso_con_significativo = crear_proceso_base(codigo="PR-01")
        proceso_sin_significativos = crear_proceso_base(codigo="PR-02")
        AspectoAmbiental.objects.create(
            proceso=proceso_con_significativo,
            codigo="ASP-01",
            nombre="A",
            impacto_asociado="I",
            es_significativo=True,
            criterio_significancia="C",
        )
        AspectoAmbiental.objects.create(
            proceso=proceso_sin_significativos,
            codigo="ASP-02",
            nombre="B",
            impacto_asociado="I",
            es_significativo=False,
            criterio_significancia="C",
        )
        con_significativos = list(servicios.procesos_del_catalogo("significativos"))
        self.assertEqual([p.codigo for p in con_significativos], ["PR-01"])
        sin_significativos = list(servicios.procesos_del_catalogo("no_significativos"))
        self.assertEqual([p.codigo for p in sin_significativos], ["PR-02"])
