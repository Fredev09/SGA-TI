from django.urls import path

from . import views

app_name = "operacion"

urlpatterns = [
    path("mediciones/nueva/", views.medicion_nueva, name="medicion_nueva"),
    path("mediciones/<uuid:medicion_id>/editar/", views.medicion_editar, name="medicion_editar"),
    path("sincronizacion/", views.sincronizacion_panel, name="sincronizacion"),
    path(
        "sincronizacion/exportar/",
        views.exportar_mediciones,
        name="exportar_mediciones",
    ),
    path(
        "sincronizacion/importar/",
        views.importar_mediciones,
        name="importar_mediciones",
    ),
]
