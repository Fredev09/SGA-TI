from django.conf import settings
from django.db import models

from core.models import ModeloVersionado


class Proceso(ModeloVersionado):
    codigo = models.CharField("código", max_length=20, unique=True)
    nombre = models.CharField("nombre", max_length=150)
    responsable = models.CharField("responsable", max_length=120)

    class Meta:
        verbose_name = "proceso"
        verbose_name_plural = "procesos"
        ordering = ["codigo"]

    def __str__(self):
        return "%s · %s" % (self.codigo, self.nombre)


class AspectoAmbiental(ModeloVersionado):
    proceso = models.ForeignKey(
        Proceso,
        on_delete=models.PROTECT,
        related_name="aspectos",
        verbose_name="proceso",
    )
    codigo = models.CharField("código", max_length=20, unique=True)
    nombre = models.CharField("nombre", max_length=150)
    impacto_asociado = models.CharField("impacto asociado", max_length=250)
    es_significativo = models.BooleanField("dictamen de significancia")
    criterio_significancia = models.CharField("criterio de significancia", max_length=300)

    class Meta:
        verbose_name = "aspecto ambiental"
        verbose_name_plural = "aspectos ambientales"
        ordering = ["codigo"]

    def __str__(self):
        return "%s · %s" % (self.codigo, self.nombre)


class Indicador(ModeloVersionado):
    aspecto = models.ForeignKey(
        AspectoAmbiental,
        on_delete=models.PROTECT,
        related_name="indicadores",
        verbose_name="aspecto ambiental",
    )
    codigo = models.CharField("código", max_length=20, unique=True)
    nombre = models.CharField("nombre", max_length=150)
    unidad_medida = models.CharField("unidad de medida", max_length=20)
    periodicidad = models.CharField("periodicidad", max_length=30)

    class Meta:
        verbose_name = "indicador"
        verbose_name_plural = "indicadores"
        ordering = ["codigo"]

    def __str__(self):
        return "%s · %s" % (self.codigo, self.nombre)


class MetaAmbiental(ModeloVersionado):
    indicador = models.ForeignKey(
        Indicador,
        on_delete=models.PROTECT,
        related_name="metas",
        verbose_name="indicador",
    )
    anio_vigencia = models.PositiveIntegerField("año de vigencia")
    valor_limite = models.DecimalField("límite mensual", max_digits=12, decimal_places=2)
    operador = models.CharField(
        "operador",
        max_length=2,
        default="<=",
        choices=[("<=", "máximo permitido (<=)")],
    )
    umbral_advertencia_pct = models.PositiveIntegerField("umbral de advertencia (%)")

    class Meta:
        verbose_name = "meta ambiental"
        verbose_name_plural = "metas ambientales"
        ordering = ["indicador__codigo", "anio_vigencia"]
        constraints = [
            models.UniqueConstraint(
                fields=["indicador", "anio_vigencia"],
                name="meta_unica_por_indicador_anio",
            ),
            models.CheckConstraint(
                condition=models.Q(operador="<="),
                name="meta_operador_mayor_igual",
                violation_error_message="Solo se admiten metas de tipo máximo permitido (<=).",
            ),
            models.CheckConstraint(
                condition=models.Q(valor_limite__gt=0),
                name="meta_valor_limite_positivo",
                violation_error_message="El límite mensual debe ser numéricamente positivo.",
            ),
            models.CheckConstraint(
                condition=models.Q(umbral_advertencia_pct__gte=50)
                & models.Q(umbral_advertencia_pct__lte=99),
                name="meta_umbral_rango",
                violation_error_message="El umbral de advertencia debe estar entre 50%% y 99%%.",
            ),
        ]

    def __str__(self):
        return "%s %s %s %s" % (self.indicador.codigo, self.anio_vigencia, self.operador, self.valor_limite)

    @property
    def valor_activacion(self):
        from decimal import ROUND_HALF_UP, Decimal

        calculo = self.valor_limite * Decimal(self.umbral_advertencia_pct) / Decimal(100)
        return calculo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class AuditoriaMeta(models.Model):
    meta = models.ForeignKey(
        MetaAmbiental,
        on_delete=models.PROTECT,
        related_name="auditorias",
        verbose_name="meta",
    )
    valor_anterior = models.DecimalField(
        "límite anterior", max_digits=12, decimal_places=2
    )
    valor_nuevo = models.DecimalField(
        "límite nuevo", max_digits=12, decimal_places=2
    )
    umbral_anterior = models.PositiveIntegerField("umbral anterior")
    umbral_nuevo = models.PositiveIntegerField("umbral nuevo")
    mediciones_recalculadas = models.PositiveIntegerField(
        "mediciones recalculadas", default=0
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="auditorias_metas",
        verbose_name="usuario",
    )
    fecha = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "auditoría de meta"
        verbose_name_plural = "auditorías de metas"
        ordering = ["-fecha"]

    def __str__(self):
        return "%s · %s → %s" % (self.meta, self.valor_anterior, self.valor_nuevo)
