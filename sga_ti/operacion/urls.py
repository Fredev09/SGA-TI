from django.urls import path

from . import views

app_name = "operacion"

urlpatterns = [
    path("mediciones/nueva/", views.medicion_nueva, name="medicion_nueva"),
    path("mediciones/<uuid:medicion_id>/editar/", views.medicion_editar, name="medicion_editar"),
]
