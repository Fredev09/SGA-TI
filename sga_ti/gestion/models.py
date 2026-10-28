import uuid as _uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from core.models import ModeloVersionado
from operacion.models import Medicion

from .almacenamiento import AlmacenEvidenciasBD

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

TIPOS_EVIDENCIA = [
    ("PDF", "PDF"),
    ("JPG", "JPG"),
    ("PNG", "PNG"),
]


def ruta_evidencia(instancia, nombre):
    return "evidencias/%s%s" % (_uuid.uuid4().hex, Path(nombre or "").suffix.lower())


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
    cerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="no_conformidades_cerradas",
        verbose_name="cerrada por",
    )
    fecha_cierre = models.DateTimeField("fecha de cierre", null=True, blank=True)

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


class AccionCorrectiva(ModeloVersionado):
    no_conformidad = models.ForeignKey(
        NoConformidad,
        on_delete=models.PROTECT,
        related_name="acciones",
        verbose_name="no conformidad",
    )
    descripcion_accion = models.TextField("descripción de la acción")
    responsable = models.CharField("responsable", max_length=150)
    fecha_limite = models.DateField("fecha límite")
    ejecutada = models.BooleanField("ejecutada", default=False)
    evaluacion_eficacia = models.TextField("evaluación de eficacia", blank=True)
    es_eficaz = models.BooleanField("es eficaz", default=False)

    class Meta:
        verbose_name = "acción correctiva"
        verbose_name_plural = "acciones correctivas"
        ordering = ["fecha_limite", "fecha_creacion"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ejecutada=True) | models.Q(es_eficaz=False),
                name="accion_eficacia_tras_ejecucion",
                violation_error_message="Una acción no puede ser eficaz antes de ejecutarse.",
            ),
        ]

    def __str__(self):
        return "%s · %s" % (self.no_conformidad.codigo, self.descripcion_accion[:60])


class EvidenciaNoConformidad(ModeloVersionado):
    no_conformidad = models.ForeignKey(
        NoConformidad,
        on_delete=models.PROTECT,
        related_name="evidencias",
        verbose_name="no conformidad",
    )
    archivo = models.FileField(
        "archivo",
        upload_to=ruta_evidencia,
        storage=AlmacenEvidenciasBD(),
        max_length=255,
    )
    nombre_original = models.CharField("nombre original", max_length=255)
    tipo = models.CharField("tipo", max_length=4, choices=TIPOS_EVIDENCIA)
    tamano = models.PositiveBigIntegerField("tamaño en bytes")
    huella = models.CharField("huella SHA-256", max_length=64)
    referencia = models.CharField("referencia documental", max_length=255)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evidencias_registradas",
        verbose_name="usuario",
    )
    fecha_carga = models.DateTimeField("fecha de carga", auto_now_add=True)

    class Meta:
        verbose_name = "evidencia de no conformidad"
        verbose_name_plural = "evidencias de no conformidades"
        ordering = ["-fecha_carga"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tamano__gt=0),
                name="evidencia_tamano_positivo",
                violation_error_message="El tamaño del archivo debe ser positivo.",
            ),
        ]

    def __str__(self):
        return "%s · %s" % (self.no_conformidad.codigo, self.nombre_original)


class ArchivoEvidencia(models.Model):
    nombre = models.CharField("nombre", max_length=255, unique=True)
    contenido = models.BinaryField("contenido")
    tamano = models.PositiveBigIntegerField("tamaño en bytes")
    creado = models.DateTimeField("fecha de creación", auto_now_add=True)

    class Meta:
        verbose_name = "archivo de evidencia"
        verbose_name_plural = "archivos de evidencia"

    def __str__(self):
        return self.nombre


class TransicionNoConformidad(models.Model):
    no_conformidad = models.ForeignKey(
        NoConformidad,
        on_delete=models.PROTECT,
        related_name="transiciones",
        verbose_name="no conformidad",
    )
    estado_anterior = models.CharField(
        "estado anterior", max_length=12, choices=ESTADOS_NC, blank=True
    )
    estado_nuevo = models.CharField("estado nuevo", max_length=12, choices=ESTADOS_NC)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="transiciones_no_conformidades",
        verbose_name="usuario",
    )
    fecha = models.DateTimeField("fecha", auto_now_add=True)
    observacion = models.CharField("observación", max_length=255, blank=True)

    class Meta:
        verbose_name = "transición de no conformidad"
        verbose_name_plural = "transiciones de no conformidades"
        ordering = ["fecha"]

    def __str__(self):
        return "%s · %s → %s" % (
            self.no_conformidad.codigo,
            self.estado_anterior or "INICIO",
            self.estado_nuevo,
        )
