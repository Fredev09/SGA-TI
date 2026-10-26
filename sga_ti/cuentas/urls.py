from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("entrada/", views.Entrada.as_view(), name="entrada"),
    path("salida/", views.Salida.as_view(), name="salida"),
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/nuevo/", views.usuario_nuevo, name="usuario_nuevo"),
    path(
        "usuarios/<uuid:usuario_id>/editar/",
        views.usuario_editar,
        name="usuario_editar",
    ),
    path(
        "usuarios/<uuid:usuario_id>/contrasena/",
        views.usuario_contrasena,
        name="usuario_contrasena",
    ),
    path(
        "usuarios/<uuid:usuario_id>/estado/",
        views.usuario_estado,
        name="usuario_estado",
    ),
    path("preferencias/", views.preferencias, name="preferencias"),
]
