from django.db import migrations


def columna_existe(schema_editor, tabla, columna):
    with schema_editor.connection.cursor() as cursor:
        columnas = schema_editor.connection.introspection.get_table_description(
            cursor,
            tabla
        )

    return columna in [col.name for col in columnas]


def reparar_jornada_id_adelanto(apps, schema_editor):
    Adelanto = apps.get_model("App_taxi", "Adelanto")
    tabla = Adelanto._meta.db_table

    if columna_existe(schema_editor, tabla, "jornada_id"):
        return

    field = Adelanto._meta.get_field("jornada")
    schema_editor.add_field(Adelanto, field)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("App_taxi", "0021_reparar_columna_jornada_adelanto"),
        ("App_taxi", "0018_merge_20260707_1515"),
    ]

    operations = [
        migrations.RunPython(
            reparar_jornada_id_adelanto,
            migrations.RunPython.noop
        ),
    ]