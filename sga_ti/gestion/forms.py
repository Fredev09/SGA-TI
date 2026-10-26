from django import forms

from .archivos import validar_evidencia
from .models import NoConformidad


class FormularioNoConformidad(forms.ModelForm):
    class Meta:
        model = NoConformidad
        fields = ["origen", "descripcion", "severidad"]
        labels = {
            "origen": "Origen del hallazgo",
            "descripcion": "Descripción del hallazgo",
            "severidad": "Severidad",
        }
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}
        error_messages = {
            "origen": {"required": "Seleccione el origen del hallazgo."},
            "descripcion": {"required": "Describa el hallazgo."},
            "severidad": {"required": "Seleccione la severidad."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["origen"].choices = [("AUDITORIA", "Auditoría"), ("MANUAL", "Manual")]


class FormularioCausaRaiz(forms.Form):
    causa_raiz = forms.CharField(
        label="Causa raíz",
        widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={"required": "Documente la causa raíz del hallazgo."},
    )


class FormularioAccion(forms.Form):
    descripcion_accion = forms.CharField(
        label="Acción correctiva",
        widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={"required": "Describa la acción correctiva."},
    )
    responsable = forms.CharField(
        label="Responsable",
        max_length=150,
        error_messages={"required": "Indique el responsable de la acción."},
    )
    fecha_limite = forms.DateField(
        label="Fecha límite",
        widget=forms.DateInput(attrs={"type": "date"}),
        error_messages={"required": "Indique la fecha límite de la acción."},
    )


class FormularioAccionEstado(forms.Form):
    ejecutada = forms.BooleanField(label="Ejecutada", required=False)
    evaluacion_eficacia = forms.CharField(
        label="Evaluación de eficacia",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    es_eficaz = forms.BooleanField(label="Eficacia satisfactoria", required=False)

    def clean(self):
        datos = super().clean()
        if datos.get("es_eficaz") and not datos.get("ejecutada"):
            raise forms.ValidationError(
                "Marque la acción como ejecutada antes de declararla eficaz."
            )
        if datos.get("es_eficaz") and not (datos.get("evaluacion_eficacia") or "").strip():
            raise forms.ValidationError(
                "Documente la evaluación de eficacia antes de declararla satisfactoria."
            )
        return datos


class FormularioEvidencia(forms.Form):
    archivo = forms.FileField(
        label="Archivo",
        help_text="PDF, JPG o PNG de hasta 5 MB.",
    )
    referencia = forms.CharField(
        label="Referencia documental",
        max_length=255,
        help_text="Documento y ubicación donde se conserva el original.",
        error_messages={"required": "Indique la referencia documental localizable."},
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        validar_evidencia(archivo)
        return archivo
