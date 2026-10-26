from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Usuario


class FormularioEntrada(AuthenticationForm):
    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos.",
        "inactive": "Esta cuenta está inactiva.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuario"
        self.fields["password"].label = "Contraseña"
        self.fields["username"].error_messages["required"] = "Ingrese su usuario."
        self.fields["password"].error_messages["required"] = "Ingrese su contraseña."
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"
        self.fields["username"].widget.attrs["placeholder"] = "Usuario"
        self.fields["password"].widget.attrs["placeholder"] = "Contraseña de acceso"


def _validar_contrasenas(formulario, usuario):
    datos = formulario.cleaned_data
    primera = datos.get("password1")
    segunda = datos.get("password2")
    if primera and segunda and primera != segunda:
        formulario.add_error("password2", "Las contraseñas no coinciden.")
    elif primera:
        try:
            validate_password(primera, usuario)
        except ValidationError as error:
            formulario.add_error("password1", error)


class FormularioUsuarioNuevo(forms.Form):
    username = forms.CharField(
        label="Usuario",
        max_length=150,
        error_messages={"required": "Ingrese el nombre de usuario."},
    )
    first_name = forms.CharField(label="Nombre", max_length=150, required=False)
    last_name = forms.CharField(label="Apellido", max_length=150, required=False)
    email = forms.EmailField(
        label="Correo",
        required=False,
        error_messages={"invalid": "Ingrese un correo válido."},
    )
    rol = forms.ChoiceField(
        label="Rol",
        choices=Usuario.Rol.choices,
        error_messages={"required": "Seleccione el rol."},
    )
    activo = forms.BooleanField(label="Cuenta activa", required=False, initial=True)
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput,
        error_messages={"required": "Asigne una contraseña."},
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput,
        error_messages={"required": "Repita la contraseña."},
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if Usuario.objects.filter(username__iexact=username).exists():
            raise ValidationError("Ya existe un usuario con ese nombre.")
        return username

    def clean(self):
        datos = super().clean()
        candidato = Usuario(
            username=datos.get("username", ""),
            email=datos.get("email", ""),
            first_name=datos.get("first_name", ""),
            last_name=datos.get("last_name", ""),
        )
        _validar_contrasenas(self, candidato)
        return datos


class FormularioUsuarioEdicion(forms.Form):
    first_name = forms.CharField(label="Nombre", max_length=150, required=False)
    last_name = forms.CharField(label="Apellido", max_length=150, required=False)
    email = forms.EmailField(
        label="Correo",
        required=False,
        error_messages={"invalid": "Ingrese un correo válido."},
    )
    rol = forms.ChoiceField(
        label="Rol",
        choices=Usuario.Rol.choices,
        error_messages={"required": "Seleccione el rol."},
    )
    activo = forms.BooleanField(label="Cuenta activa", required=False)


class FormularioContrasena(forms.Form):
    password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput,
        error_messages={"required": "Asigne una contraseña."},
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput,
        error_messages={"required": "Repita la contraseña."},
    )

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean(self):
        datos = super().clean()
        _validar_contrasenas(self, self.usuario or Usuario())
        return datos
