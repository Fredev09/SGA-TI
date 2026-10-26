from django.db import models

from core.models import ModeloVersionado
from operacion.models import Medicion

ORIGENES = [
    ("AUTOMATICA", "Automática"),
    ("AUDITORIA", "Auditoría"),
    ("MANUAL", "Manual"),
]

ESTADOS_NC = [
    ("ABIERTA", "Abierta"),
    ("EN_ANALISIS", "En análisis"),
    ("CERRADA", "Cerrada"),
]

SEVERIDADES = [
    ("Baja", "Baja"),
    ("Media", "Media"),
    ("Alta", "Alta"),
]


class NoConformidad(ModeloVersionado):
    medicion = models.ForeignKey(
        Medicion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="no_conformidades",
        verbose_name="medición",
    )
    origen = models.CharField("origen", max_length=10, choices=ORIGENES)
    codigo = models.CharField("código", max_length=20, unique=True)
    fecha_deteccion = models.DateTimeField("fecha de detección")
    descripcion = models.TextField("descripción")
    severidad = models.CharField("severidad", max_length=5, choices=SEVERIDADES)
    causa_raiz = models.TextField("causa raíz", blank=True)
    estado = models.CharField("estado", max_length=12, choices=ESTADOS_NC, default="ABIERTA")
    requiere_revision = models.BooleanField("requiere revisión", default=False)

    class Meta:
        verbose_name = "no conformidad"
        verbose_name_plural = "no conformidades"
        ordering = ["-fecha_deteccion"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(origen__in=["AUTOMATICA", "AUDITORIA", "MANUAL"]),
                name="nc_origen_valido",
                violation_error_message="El origen debe ser AUTOMATICA, AUDITORIA o MANUAL.",
            ),
            models.CheckConstraint(
                condition=models.Q(estado__in=["ABIERTA", "EN_ANALISIS", "CERRADA"]),
                name="nc_estado_valido",
                violation_error_message="El estado debe ser ABIERTA, EN_ANALISIS o CERRADA.",
            ),
            models.CheckConstraint(
                condition=~models.Q(origen="AUTOMATICA") | models.Q(medicion__isnull=False),
                name="nc_automatica_con_medicion",
                violation_error_message="El origen automático exige una medición asociada.",
            ),
        ]

    def __str__(self):
        return "%s · %s" % (self.codigo, self.descripcion[:60])

    @property
    def activa(self):
        return self.estado != "CERRADA"
