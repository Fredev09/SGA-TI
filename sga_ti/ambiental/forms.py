from django import forms

from .models import AspectoAmbiental, Proceso


class FormularioProceso(forms.ModelForm):
    class Meta:
        model = Proceso
        fields = ["codigo", "nombre", "responsable"]
        error_messages = {
            "codigo": {
                "required": "Ingrese el código del proceso.",
                "unique": "Ya existe un proceso con ese código.",
            },
            "nombre": {"required": "Ingrese el nombre del proceso."},
            "responsable": {"required": "Ingrese el responsable del proceso."},
        }


class FormularioAspecto(forms.ModelForm):
    es_significativo = forms.ChoiceField(
        label="Dictamen de significancia",
        choices=[("", "Seleccione una opción"), ("1", "Significativo"), ("0", "No significativo")],
        error_messages={"required": "Elija el dictamen de significancia."},
    )

    class Meta:
        model = AspectoAmbiental
        fields = [
            "proceso",
            "codigo",
            "nombre",
            "impacto_asociado",
            "es_significativo",
            "criterio_significancia",
        ]
        error_messages = {
            "proceso": {"required": "Seleccione el proceso."},
            "codigo": {
                "required": "Ingrese el código del aspecto.",
                "unique": "Ya existe un aspecto con ese código.",
            },
            "nombre": {"required": "Ingrese el nombre del aspecto."},
            "impacto_asociado": {"required": "Describa el impacto asociado."},
            "criterio_significancia": {"required": "Describa el criterio de significancia."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["criterio_significancia"].widget = forms.Textarea(attrs={"rows": 3})

    def clean_es_significativo(self):
        return self.cleaned_data["es_significativo"] == "1"
