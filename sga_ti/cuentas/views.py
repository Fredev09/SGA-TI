from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import seguridad, servicios
from .forms import (
    FormularioContrasena,
    FormularioEntrada,
    FormularioUsuarioEdicion,
    FormularioUsuarioNuevo,
)
from .models import Usuario
from .permisos import requiere_rol


class Entrada(LoginView):
    template_name = "cuentas/entrada.html"
    authentication_form = FormularioEntrada
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        username = (request.POST.get("username") or "").strip()
        if username and seguridad.esta_bloqueado(request, username):
            messages.error(
                request,
                "Cuenta bloqueada por %d minutos tras %d intentos fallidos."
                % (seguridad.BLOQUEO_SEGUNDOS // 60, seguridad.MAX_INTENTOS),
            )
            return self.render_to_response(
                self.get_context_data(form=self.get_form_class()(request=request))
            )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        seguridad.limpiar_intentos(self.request, form.cleaned_data.get("username", ""))
        return super().form_valid(form)

    def form_invalid(self, form):
        errores = form.errors.as_data().get("__all__", ())
        if any(error.code == "invalid_login" for error in errores):
            username = (self.request.POST.get("username") or "").strip()
            restantes = seguridad.registrar_fallo(self.request, username)
            if restantes > 0:
                messages.warning(
                    self.request,
                    "Credenciales incorrectas. Te quedan %d intento%s."
                    % (restantes, "" if restantes == 1 else "s"),
                )
            else:
                messages.error(
                    self.request,
                    "Cuenta bloqueada por %d minutos tras %d intentos fallidos."
                    % (seguridad.BLOQUEO_SEGUNDOS // 60, seguridad.MAX_INTENTOS),
                )
        return super().form_invalid(form)


class Salida(LogoutView):
    pass


@requiere_rol("modificar_usuarios")
def usuarios(request):
    return render(
        request,
        "cuentas/usuarios.html",
        {"usuarios": Usuario.objects.order_by("username")},
    )


@requiere_rol("modificar_usuarios")
def usuario_nuevo(request):
    formulario = FormularioUsuarioNuevo(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        datos = formulario.cleaned_data
        try:
            usuario = servicios.crear_usuario(
                username=datos["username"],
                password=datos["password1"],
                rol=datos["rol"],
                first_name=datos["first_name"],
                last_name=datos["last_name"],
                email=datos["email"],
                activo=datos["activo"],
            )
        except ValidationError as error:
            formulario.add_error("password1", error)
        else:
            messages.success(request, "Usuario %s creado." % usuario.username)
            return redirect("cuentas:usuarios")
    return render(
        request,
        "cuentas/usuario_formulario.html",
        {"form": formulario, "creando": True},
    )


@requiere_rol("modificar_usuarios")
def usuario_editar(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    inicial = {
        "first_name": usuario.first_name,
        "last_name": usuario.last_name,
        "email": usuario.email,
        "rol": usuario.rol,
        "activo": usuario.is_active,
    }
    formulario = FormularioUsuarioEdicion(request.POST or None, initial=inicial)
    if request.method == "POST" and formulario.is_valid():
        datos = formulario.cleaned_data
        try:
            servicios.actualizar_usuario(
                usuario=usuario,
                first_name=datos["first_name"],
                last_name=datos["last_name"],
                email=datos["email"],
                rol=datos["rol"],
                activo=datos["activo"],
                actor=request.user,
            )
        except ValidationError as error:
            formulario.add_error(None, error)
        else:
            messages.success(request, "Usuario %s actualizado." % usuario.username)
            return redirect("cuentas:usuarios")
    return render(
        request,
        "cuentas/usuario_formulario.html",
        {"form": formulario, "creando": False, "usuario": usuario},
    )


@requiere_rol("modificar_usuarios")
@require_POST
def usuario_estado(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    try:
        servicios.alternar_activo(
            usuario=usuario, activo=not usuario.is_active, actor=request.user
        )
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        estado = "activada" if usuario.is_active else "desactivada"
        messages.success(request, "Cuenta %s %s." % (usuario.username, estado))
    return redirect("cuentas:usuarios")


@requiere_rol("modificar_usuarios")
def usuario_contrasena(request, usuario_id):
    usuario = get_object_or_404(Usuario, pk=usuario_id)
    formulario = FormularioContrasena(request.POST or None, usuario=usuario)
    if request.method == "POST" and formulario.is_valid():
        try:
            servicios.cambiar_contrasena(
                usuario=usuario, password=formulario.cleaned_data["password1"]
            )
        except ValidationError as error:
            formulario.add_error("password1", error)
        else:
            messages.success(
                request, "Contraseña actualizada para %s." % usuario.username
            )
            return redirect("cuentas:usuarios")
    return render(
        request,
        "cuentas/contrasena.html",
        {"form": formulario, "usuario": usuario},
    )


@login_required
def preferencias(request):
    return render(request, "cuentas/preferencias.html")
