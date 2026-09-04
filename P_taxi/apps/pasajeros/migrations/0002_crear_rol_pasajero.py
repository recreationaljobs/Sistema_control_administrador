from django.db import migrations


def crear_rol_pasajero(
    apps,
    schema_editor,
):
    Rol = apps.get_model(
        "App_taxi",
        "Rol",
    )

    Rol.objects.update_or_create(
        codigo="pasajero",
        defaults={
            "nombre": "Pasajero",
            "activo": True,
        },
    )


def eliminar_rol_pasajero(
    apps,
    schema_editor,
):
    Rol = apps.get_model(
        "App_taxi",
        "Rol",
    )

    Rol.objects.filter(
        codigo="pasajero",
        usuarios__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "pasajeros",
            "0001_initial",
        ),
        (
            "App_taxi",
            "0030_vehiculo_tipo_vehiculo",
        ),
    ]

    operations = [
        migrations.RunPython(
            crear_rol_pasajero,
            eliminar_rol_pasajero,
        ),
    ]