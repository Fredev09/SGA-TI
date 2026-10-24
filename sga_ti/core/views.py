from django.shortcuts import render

from cuentas.permisos import requiere_rol


@requiere_rol("ver_dashboard")
def inicio(request):
    return render(request, "core/inicio.html")
