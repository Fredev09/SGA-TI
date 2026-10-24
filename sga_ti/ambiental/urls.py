from django.urls import path

from . import views

app_name = "ambiental"

urlpatterns = [
    path("catalogo/", views.catalogo, name="catalogo"),
    path("catalogo/procesos/nuevo/", views.proceso_nuevo, name="proceso_nuevo"),
    path("catalogo/aspectos/nuevo/", views.aspecto_nuevo, name="aspecto_nuevo"),
]
