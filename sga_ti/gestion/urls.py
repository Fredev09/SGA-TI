from django.urls import path

from . import views

app_name = "gestion"

urlpatterns = [
    path("no-conformidades/", views.lista, name="lista"),
    path("no-conformidades/nueva/", views.nueva, name="nueva"),
    path("no-conformidades/<uuid:nc_id>/", views.detalle, name="detalle"),
    path("no-conformidades/<uuid:nc_id>/causa/", views.causa_raiz, name="causa_raiz"),
    path("no-conformidades/<uuid:nc_id>/acciones/", views.nueva_accion, name="nueva_accion"),
    path(
        "no-conformidades/<uuid:nc_id>/acciones/<uuid:accion_id>/",
        views.actualizar_accion,
        name="actualizar_accion",
    ),
    path(
        "no-conformidades/<uuid:nc_id>/evidencias/",
        views.nueva_evidencia,
        name="nueva_evidencia",
    ),
    path("no-conformidades/<uuid:nc_id>/cerrar/", views.cerrar, name="cerrar"),
    path(
        "no-conformidades/<uuid:nc_id>/evidencias/<uuid:evidencia_id>/descargar/",
        views.descargar_evidencia,
        name="descargar_evidencia",
    ),
]
