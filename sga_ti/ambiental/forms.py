from django import forms

from .models import AspectoAmbiental, Indicador, MetaAmbiental, Proceso


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


class FormularioIndicador(forms.ModelForm):
    class Meta:
        model = Indicador
        fields = ["aspecto", "codigo", "nombre", "unidad_medida", "periodicidad"]
        error_messages = {
            "aspecto": {"required": "Seleccione el aspecto ambiental."},
            "codigo": {
                "required": "Ingrese el código del indicador.",
                "unique": "Ya existe un indicador con ese código.",
            },
            "nombre": {"required": "Ingrese el nombre del indicador."},
            "unidad_medida": {"required": "Ingrese la unidad de medida del indicador."},
            "periodicidad": {"required": "Ingrese la periodicidad del indicador."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["periodicidad"].initial = "Mensual"
        self.fields["unidad_medida"].help_text = "Por ejemplo: kWh, m3 o kg."
        self.fields["periodicidad"].help_text = "Seguimiento mensual del indicador."


class FormularioMeta(forms.ModelForm):
    class Meta:
        model = MetaAmbiental
        fields = ["indicador", "anio_vigencia", "valor_limite", "umbral_advertencia_pct"]
        labels = {
            "indicador": "Indicador",
            "anio_vigencia": "Año de vigencia",
            "valor_limite": "Límite mensual permitido",
            "umbral_advertencia_pct": "Umbral de advertencia (%)",
        }
        error_messages = {
            "indicador": {"required": "Seleccione el indicador."},
            "anio_vigencia": {"required": "Ingrese el año de vigencia de la meta."},
            "valor_limite": {
                "required": "Ingrese el límite mensual de la meta.",
                "invalid": "El límite mensual debe ser un número.",
            },
            "umbral_advertencia_pct": {
                "required": "Ingrese el umbral de advertencia.",
                "invalid": "El umbral de advertencia debe ser un número.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["anio_vigencia"].help_text = "Ejercicio fiscal en que rige la meta."
        self.fields["valor_limite"].help_text = "Máximo mensual permitido, numérico positivo."
        self.fields["umbral_advertencia_pct"].help_text = "Entre 50 y 99 por ciento."


class FormularioMetaEdicion(forms.ModelForm):
    class Meta:
        model = MetaAmbiental
        fields = ["valor_limite", "umbral_advertencia_pct"]
        labels = {
            "valor_limite": "Límite mensual permitido",
            "umbral_advertencia_pct": "Umbral de advertencia (%)",
        }
        error_messages = {
            "valor_limite": {
                "required": "Ingrese el límite mensual de la meta.",
                "invalid": "El límite mensual debe ser un número.",
            },
            "umbral_advertencia_pct": {
                "required": "Ingrese el umbral de advertencia.",
                "invalid": "El umbral de advertencia debe ser un número.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["valor_limite"].help_text = "Máximo mensual permitido, numérico positivo."
        self.fields["umbral_advertencia_pct"].help_text = "Entre 50 y 99 por ciento."
