from django.db import migrations

FUNCION = """
CREATE OR REPLACE FUNCTION sga_ti_registro_historico() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Operacion no permitida sobre un registro historico.';
END;
$$ LANGUAGE plpgsql;
"""

TRIGGERS = (
    "CREATE TRIGGER operacion_medicion_sin_borrado BEFORE DELETE ON operacion_medicion "
    "FOR EACH ROW EXECUTE FUNCTION sga_ti_registro_historico();",
    "CREATE TRIGGER operacion_auditoria_sin_actualizacion BEFORE UPDATE ON operacion_auditoriamedicion "
    "FOR EACH ROW EXECUTE FUNCTION sga_ti_registro_historico();",
    "CREATE TRIGGER operacion_auditoria_sin_borrado BEFORE DELETE ON operacion_auditoriamedicion "
    "FOR EACH ROW EXECUTE FUNCTION sga_ti_registro_historico();",
)

NOMBRES_MEDICION = ("operacion_medicion_sin_borrado",)
NOMBRES_AUDITORIA = (
    "operacion_auditoria_sin_actualizacion",
    "operacion_auditoria_sin_borrado",
)


def aplicar(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(FUNCION)
    for sentencia in TRIGGERS:
        schema_editor.execute(sentencia)


def revertir(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for nombre in NOMBRES_MEDICION:
        schema_editor.execute("DROP TRIGGER IF EXISTS %s ON operacion_medicion;" % nombre)
    for nombre in NOMBRES_AUDITORIA:
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS %s ON operacion_auditoriamedicion;" % nombre
        )
    schema_editor.execute("DROP FUNCTION IF EXISTS sga_ti_registro_historico();")


class Migration(migrations.Migration):
    dependencies = [("operacion", "0002_inmutabilidad")]

    operations = [migrations.RunPython(aplicar, revertir)]
