from django.db import models

from ambiental.models import Indicador
from core.models import ModeloVersionado

MESES = [
    (1, "Enero"),
    (2, "Febrero"),
    (3, "Marzo"),
    (4, "Abril"),
    (5, "Mayo"),
    (6, "Junio"),
    (7, "Julio"),
    (8, "Agosto"),
    (9, "Septiembre"),
    (10, "Octubre"),
    (11, "Noviembre"),
    (12, "Diciembre"),
]

MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

ESTADOS_SEMAFORO = [
    ("NORMAL", "Normal"),
    ("ADVERTENCIA", "Advertencia"),
    ("ALERTA", "Alerta"),
]


class Medicion(ModeloVersionado):
    indicador = models.ForeignKey(
        Indicador,
        on_delete=models.PROTECT,
        related_name="mediciones",
        verbose_name="indicador",
    )
    anio = models.PositiveIntegerField("año")
    mes = models.PositiveIntegerField("mes")
    valor_medido = models.DecimalField("valor medido", max_digits=12, decimal_places=2)
    valor_meta = models.DecimalField("valor de la meta", max_digits=12, decimal_places=2)
    desvio_pct = models.DecimalField("desvío (%)", max_digits=7, decimal_places=2)
    estado_semaforo = models.CharField(
        "estado del semáforo",
        max_length=12,
        choices=ESTADOS_SEMAFORO,
    )
    usuario = models.ForeignKey(
        "cuentas.Usuario",
        on_delete=models.PROTECT,
        related_name="mediciones",
        verbose_name="usuario",
    )
    evidencia = models.CharField("evidencia documental", max_length=250)

    class Meta:
        verbose_name = "medición"
        verbose_name_plural = "mediciones"
        ordering = ["-anio", "-mes", "indicador__codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["indicador", "anio", "mes"],
                name="medicion_unica_por_indicador_periodo",
            ),
            models.CheckConstraint(
                condition=models.Q(mes__gte=1) & models.Q(mes__lte=12),
                name="medicion_mes_rango",
                violation_error_message="El mes debe estar entre 1 y 12.",
            ),
            models.CheckConstraint(
                condition=models.Q(valor_medido__gte=0),
                name="medicion_valor_no_negativo",
                violation_error_message="El valor medido debe ser numérico positivo o cero.",
            ),
        ]

    def __str__(self):
        return "%s %s/%s" % (self.indicador.codigo, self.mes, self.anio)

    @property
    def fecha_registro(self):
        return self.fecha_creacion

    @property
    def nombre_mes(self):
        return dict(MESES).get(self.mes, "")


class AuditoriaMedicion(models.Model):
    medicion = models.ForeignKey(
        Medicion,
        on_delete=models.PROTECT,
        related_name="auditorias",
        verbose_name="medición",
    )
    valor_anterior = models.DecimalField("valor anterior", max_digits=12, decimal_places=2)
    valor_nuevo = models.DecimalField("valor nuevo", max_digits=12, decimal_places=2)
    usuario = models.ForeignKey(
        "cuentas.Usuario",
        on_delete=models.PROTECT,
        related_name="auditorias_mediciones",
        verbose_name="usuario",
    )
    fecha_modificacion = models.DateTimeField("fecha de modificación", auto_now_add=True)

    class Meta:
        verbose_name = "auditoría de medición"
        verbose_name_plural = "auditorías de mediciones"
        ordering = ["-fecha_modificacion"]

    def __str__(self):
        return "%s · %s → %s" % (self.medicion, self.valor_anterior, self.valor_nuevo)


class AuditoriaEvaluacion(models.Model):
    medicion = models.ForeignKey(
        Medicion,
        on_delete=models.PROTECT,
        related_name="evaluaciones",
        verbose_name="medición",
    )
    valor_meta_anterior = models.DecimalField(
        "meta anterior", max_digits=12, decimal_places=2
    )
    valor_meta_nuevo = models.DecimalField(
        "meta nueva", max_digits=12, decimal_places=2
    )
    desvio_anterior = models.DecimalField(
        "desvío anterior", max_digits=12, decimal_places=2
    )
    desvio_nuevo = models.DecimalField(
        "desvío nuevo", max_digits=12, decimal_places=2
    )
    estado_anterior = models.CharField(
        "estado anterior", max_length=20, choices=ESTADOS_SEMAFORO
    )
    estado_nuevo = models.CharField(
        "estado nuevo", max_length=20, choices=ESTADOS_SEMAFORO
    )
    usuario = models.ForeignKey(
        "cuentas.Usuario",
        on_delete=models.PROTECT,
        related_name="auditorias_evaluaciones",
        verbose_name="usuario",
    )
    motivo = models.CharField("motivo", max_length=120, default="Meta actualizada")
    fecha = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "auditoría de evaluación"
        verbose_name_plural = "auditorías de evaluaciones"
        ordering = ["-fecha"]

    def __str__(self):
        return "%s · %s → %s" % (self.medicion, self.estado_anterior, self.estado_nuevo)
