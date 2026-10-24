from django.http import HttpResponse
from django.urls import include, path

from cuentas.permisos import requiere_rol


@requiere_rol("modificar_usuarios")
def vista_restringida(request):
    return HttpResponse("acceso concedido")


urlpatterns = [
    path("", include("core.urls")),
    path("", include("cuentas.urls")),
    path("zona-restringida/", vista_restringida),
]
