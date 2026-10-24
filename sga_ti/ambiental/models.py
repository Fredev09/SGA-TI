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
