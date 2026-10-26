from django.db import migrations

TRIGGERS = (
    (
        "operacion_medicion_sin_borrado",
        "BEFORE DELETE ON operacion_medicion",
        "Las mediciones historicas no se eliminan.",
    ),
    (
        "operacion_auditoria_sin_actualizacion",
        "BEFORE UPDATE ON operacion_auditoriamedicion",
        "La bitacora de auditoria es de solo lectura.",
    ),
    (
        "operacion_auditoria_sin_borrado",
        "BEFORE DELETE ON operacion_auditoriamedicion",
        "La bitacora de auditoria es de solo lectura.",
    ),
)


def aplicar(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    for nombre, evento, mensaje in TRIGGERS:
        schema_editor.execute(
            "CREATE TRIGGER IF NOT EXISTS %s %s BEGIN SELECT RAISE(ABORT, '%s'); END;"
            % (nombre, evento, mensaje)
        )


def revertir(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return
    for nombre, evento, mensaje in TRIGGERS:
        schema_editor.execute("DROP TRIGGER IF EXISTS %s;" % nombre)


class Migration(migrations.Migration):
    dependencies = [("operacion", "0001_initial")]

    operations = [migrations.RunPython(aplicar, revertir)]
