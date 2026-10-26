from django.urls import path

from . import views

app_name = "ambiental"

urlpatterns = [
    path("catalogo/", views.catalogo, name="catalogo"),
    path("catalogo/procesos/nuevo/", views.proceso_nuevo, name="proceso_nuevo"),
    path("catalogo/aspectos/nuevo/", views.aspecto_nuevo, name="aspecto_nuevo"),
    path("parametrizacion/", views.parametrizacion, name="parametrizacion"),
    path("parametrizacion/indicadores/nuevo/", views.indicador_nuevo, name="indicador_nuevo"),
    path("parametrizacion/metas/nueva/", views.meta_nueva, name="meta_nueva"),
    path(
        "parametrizacion/metas/<uuid:meta_id>/editar/",
        views.meta_editar,
        name="meta_editar",
    ),
]
