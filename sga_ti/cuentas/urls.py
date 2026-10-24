from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("entrada/", views.Entrada.as_view(), name="entrada"),
    path("salida/", views.Salida.as_view(), name="salida"),
]
