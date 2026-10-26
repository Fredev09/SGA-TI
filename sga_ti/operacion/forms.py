from decimal import Decimal

from django import forms

from ambiental.models import Indicador

from .models import MESES


class FormularioPeriodo(forms.Form):
    indicador = forms.ModelChoiceField(
        label="Indicador ambiental",
        queryset=Indicador.objects.select_related("aspecto").order_by("codigo"),
        empty_label="Seleccione una opción",
        error_messages={"required": "Seleccione el indicador ambiental."},
    )
    anio = forms.IntegerField(
        label="Año",
        min_value=1000,
        max_value=9999,
        error_messages={
            "required": "Ingrese el año del periodo.",
            "invalid": "Ingrese un año de periodo válido.",
            "min_value": "Ingrese un año de periodo válido.",
            "max_value": "Ingrese un año de periodo válido.",
        },
    )
    mes = forms.TypedChoiceField(
        label="Mes de corte",
        choices=MESES,
        coerce=int,
        error_messages={
            "required": "Seleccione el mes del periodo.",
            "invalid_choice": "Seleccione el mes del periodo.",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["indicador"].help_text = "Debe tener meta vigente en el año del periodo."
        self.fields["anio"].widget = forms.NumberInput(attrs={"min": 1000, "max": 9999})
        self.fields["anio"].help_text = "Ejercicio en que se registra la medición."
        self.fields["mes"].help_text = "Corte mensual del consumo o generación."


class FormularioValor(forms.Form):
    valor_medido = forms.DecimalField(
        label="Valor medido",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal(0),
        localize=True,
        error_messages={
            "required": "Ingrese el valor medido.",
            "invalid": "Introduzca un número.",
            "min_value": "El valor medido debe ser numérico positivo o cero.",
        },
    )
    evidencia = forms.CharField(
        label="Evidencia documental de respaldo",
        max_length=250,
        error_messages={
            "required": "Ingrese la referencia de la evidencia documental de respaldo.",
            "max_length": "La evidencia no puede superar 250 caracteres.",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["valor_medido"].widget = forms.TextInput(
            attrs={"inputmode": "decimal", "autocomplete": "off"}
        )
        self.fields["valor_medido"].help_text = "Valor del periodo en la unidad del indicador."
        self.fields["evidencia"].widget = forms.Textarea(attrs={"rows": 2})
        self.fields["evidencia"].help_text = (
            "Por ejemplo: factura, reporte de sensor o acta de entrega."
        )
