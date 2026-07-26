from App_taxi.models import (
    EstadoMantenimiento,
    TipoMantenimiento,
)


def corregir_estado(nombre, codigo):
    estado = (
        EstadoMantenimiento.objects
        .filter(nombre__iexact=nombre)
        .first()
    )

    if not estado:
        estado = EstadoMantenimiento(
            nombre=nombre
        )

    estado.codigo = codigo
    estado.activo = True
    estado.save()

    print(
        "Estado:",
        estado.nombre,
        "=>",
        estado.codigo,
    )


def corregir_tipo(nombre, codigo):
    tipo = (
        TipoMantenimiento.objects
        .filter(nombre__iexact=nombre)
        .first()
    )

    if not tipo:
        tipo = TipoMantenimiento(
            nombre=nombre,
            intervalo_km=5000,
        )

    tipo.codigo = codigo
    tipo.activo = True
    tipo.save()

    print(
        "Tipo:",
        tipo.nombre,
        "=>",
        tipo.codigo,
    )


corregir_estado(
    "Cancelado",
    "cancelado",
)

corregir_estado(
    "En curso",
    "en_curso",
)

corregir_estado(
    "Finalizado",
    "finalizado",
)

corregir_estado(
    "Pendiente",
    "pendiente",
)

corregir_tipo(
    "Aceite",
    "aceite",
)

corregir_tipo(
    "Mantenimiento",
    "mantenimiento",
)
