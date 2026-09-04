from django.db import migrations


TIPOS_INICIALES = (
    {
        "codigo": "taxi",
        "nombre": "Taxi",
        "descripcion": (
            "Automóvil para transporte "
            "de pasajeros."
        ),
        "capacidad_pasajeros": 4,
        "permite_equipaje": True,
        "requiere_casco": False,
        "orden": 10,
    },
    {
        "codigo": "mototaxi",
        "nombre": "Mototaxi",
        "descripcion": (
            "Mototaxi para recorridos "
            "urbanos."
        ),
        "capacidad_pasajeros": 3,
        "permite_equipaje": False,
        "requiere_casco": False,
        "orden": 20,
    },
    {
        "codigo": "moto",
        "nombre": "Moto",
        "descripcion": (
            "Motocicleta para un pasajero."
        ),
        "capacidad_pasajeros": 1,
        "permite_equipaje": False,
        "requiere_casco": True,
        "orden": 30,
    },
)


def cargar_tipos_iniciales(
    apps,
    schema_editor,
):
    TipoVehiculo = apps.get_model(
        "flota",
        "TipoVehiculo",
    )

    Vehiculo = apps.get_model(
        "App_taxi",
        "Vehiculo",
    )

    tipos = {}

    for datos in TIPOS_INICIALES:
        codigo = datos["codigo"]

        tipo, _creado = (
            TipoVehiculo.objects
            .update_or_create(
                codigo=codigo,
                defaults={
                    **datos,
                    "activo": True,
                },
            )
        )

        tipos[codigo] = tipo

    Vehiculo.objects.filter(
        tipo_vehiculo__isnull=True
    ).update(
        tipo_vehiculo=tipos["taxi"]
    )


def revertir_tipos_iniciales(
    apps,
    schema_editor,
):
    TipoVehiculo = apps.get_model(
        "flota",
        "TipoVehiculo",
    )

    Vehiculo = apps.get_model(
        "App_taxi",
        "Vehiculo",
    )

    codigos = [
        tipo["codigo"]
        for tipo in TIPOS_INICIALES
    ]

    tipos = TipoVehiculo.objects.filter(
        codigo__in=codigos
    )

    Vehiculo.objects.filter(
        tipo_vehiculo__in=tipos
    ).update(
        tipo_vehiculo=None
    )

    tipos.delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "flota",
            "0001_initial",
        ),
        (
            "App_taxi",
            "0030_vehiculo_tipo_vehiculo",
        ),
    ]

    operations = [
        migrations.RunPython(
            cargar_tipos_iniciales,
            revertir_tipos_iniciales,
        ),
    ]