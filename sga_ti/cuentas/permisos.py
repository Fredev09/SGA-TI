from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Usuario

ACCIONES = {
    "ver_dashboard": (Usuario.Rol.OPERADOR, Usuario.Rol.RESPONSABLE_SGA),
    "registrar_medicion": (Usuario.Rol.OPERADOR, Usuario.Rol.RESPONSABLE_SGA),
    "editar_medicion": (Usuario.Rol.OPERADOR, Usuario.Rol.RESPONSABLE_SGA),
    "modificar_procesos": (Usuario.Rol.RESPONSABLE_SGA,),
    "modificar_aspectos": (Usuario.Rol.RESPONSABLE_SGA,),
    "modificar_indicadores": (Usuario.Rol.RESPONSABLE_SGA,),
    "modificar_metas": (Usuario.Rol.RESPONSABLE_SGA,),
    "modificar_usuarios": (Usuario.Rol.RESPONSABLE_SGA,),
    "gestionar_no_conformidades": (Usuario.Rol.RESPONSABLE_SGA,),
    "cerrar_no_conformidades": (Usuario.Rol.RESPONSABLE_SGA,),
    "generar_reportes": (Usuario.Rol.RESPONSABLE_SGA,),
}


def puede(usuario, accion):
    if not usuario.is_authenticated:
        return False
    roles_permitidos = ACCIONES.get(accion)
    if roles_permitidos is None:
        return False
    return usuario.rol in roles_permitidos


def requiere_rol(accion):
    if accion not in ACCIONES:
        raise ValueError("Acción desconocida: %s" % accion)

    def envoltura(vista):
        @login_required
        @wraps(vista)
        def interna(request, *args, **kwargs):
            if not puede(request.user, accion):
                raise PermissionDenied
            return vista(request, *args, **kwargs)
        return interna
    return envoltura
