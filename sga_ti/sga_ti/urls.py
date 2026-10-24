from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("", include("cuentas.urls")),
    path("", include("ambiental.urls")),
]
