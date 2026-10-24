from django.contrib.auth.views import LoginView, LogoutView

from .forms import FormularioEntrada


class Entrada(LoginView):
    template_name = "cuentas/entrada.html"
    authentication_form = FormularioEntrada
    redirect_authenticated_user = True


class Salida(LogoutView):
    pass
