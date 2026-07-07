
from django.db import migrations


def reparar_columnas_conductor(apps, schema_editor):
    Conductor = apps.get_model("App_taxi", "Conductor")
    tabla = Conductor._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"SHOW COLUMNS FROM `{tabla}`")
        columnas = {fila[0] for fila in cursor.fetchall()}

        if "licencia" not in columnas:
            cursor.execute(
                f"""
                ALTER TABLE `{tabla}`
                ADD COLUMN `licencia` VARCHAR(50) NOT NULL DEFAULT ''
                """
            )

        if "vencimiento_licencia" not in columnas:
            cursor.execute(
                f"""
                ALTER TABLE `{tabla}`
                ADD COLUMN `vencimiento_licencia` DATE NULL
                """
            )

        if "numero_licencia" not in columnas:
            cursor.execute(
                f"""
                ALTER TABLE `{tabla}`
                ADD COLUMN `numero_licencia` VARCHAR(50) NULL
                """
            )

        if "fecha_inicio_licencia" not in columnas:
            cursor.execute(
                f"""
                ALTER TABLE `{tabla}`
                ADD COLUMN `fecha_inicio_licencia` DATE NULL
                """
            )

        if "fecha_vencimiento_licencia" not in columnas:
            cursor.execute(
                f"""
                ALTER TABLE `{tabla}`
                ADD COLUMN `fecha_vencimiento_licencia` DATE NULL
                """
            )

        if "porcentaje_pago" not in columnas:
            cursor.execute(
                f"""
                ALTER TABLE `{tabla}`
                ADD COLUMN `porcentaje_pago` DECIMAL(5,2) NOT NULL DEFAULT 30.00
                """
            )

        if "activo" not in columnas:
            cursor.execute(
                f"""
                ALTER TABLE `{tabla}`
                ADD COLUMN `activo` TINYINT(1) NOT NULL DEFAULT 1
                """
            )


class Migration(migrations.Migration):

    dependencies = [
        ("App_taxi", "0015_reparar_columnas_conductor"),
    ]

    operations = [
        migrations.RunPython(
            reparar_columnas_conductor,
            migrations.RunPython.noop
        ),
    ]