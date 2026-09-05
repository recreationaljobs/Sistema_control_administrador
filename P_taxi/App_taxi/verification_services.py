"""Servicios para aprobar o bloquear conductores y sus vehículos."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from App_taxi.models import (
    AsignacionVehiculo,
    Conductor,
    EstadoVehiculo,
    Vehiculo,
)


def _obtener_vehiculo_registrado(conductor):
    vehiculo = (
        Vehiculo.objects.select_for_update()
        .select_related("tipo_vehiculo")
        .filter(
            propietario_conductor=conductor,
            tipo_propiedad="conductor",
        )
        .exclude(estado_verificacion="rechazado")
        .order_by("-fecha_registro")
        .first()
    )

    if not vehiculo:
        raise ValidationError(
            "El conductor no tiene un vehículo pendiente de aprobación."
        )

    return vehiculo


@transaction.atomic
def aprobar_conductor_completo(conductor_id):
    """Aprueba conductor, vehículo y asignación como una sola operación."""
    conductor = (
        Conductor.objects.select_for_update()
        .select_related("sucursal")
        .get(pk=conductor_id)
    )
    vehiculo = _obtener_vehiculo_registrado(conductor)

    estado_activo = (
        EstadoVehiculo.objects.filter(
            codigo="activo",
            activo=True,
        ).first()
    )

    if not estado_activo:
        raise ValidationError(
            "No existe un estado de vehículo activo configurado."
        )

    conflicto_conductor = (
        AsignacionVehiculo.objects.select_for_update()
        .filter(conductor=conductor, activa=True)
        .exclude(vehiculo=vehiculo)
        .first()
    )
    if conflicto_conductor:
        raise ValidationError(
            "El conductor ya tiene otro vehículo asignado."
        )

    conflicto_vehiculo = (
        AsignacionVehiculo.objects.select_for_update()
        .filter(vehiculo=vehiculo, activa=True)
        .exclude(conductor=conductor)
        .first()
    )
    if conflicto_vehiculo:
        raise ValidationError(
            "El vehículo ya está asignado a otro conductor."
        )

    conductor.estado_verificacion = "aprobado"
    conductor.activo = True
    conductor.save(
        update_fields=[
            "estado_verificacion",
            "activo",
        ]
    )

    vehiculo.estado_verificacion = "aprobado"
    vehiculo.estado = estado_activo
    vehiculo.motivo_rechazo = ""
    vehiculo.save(
        update_fields=[
            "estado_verificacion",
            "estado",
            "motivo_rechazo",
        ]
    )

    asignacion = (
        AsignacionVehiculo.objects.select_for_update()
        .filter(
            conductor=conductor,
            vehiculo=vehiculo,
        )
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    if asignacion:
        asignacion.sucursal = vehiculo.sucursal or conductor.sucursal
        asignacion.fecha_inicio = timezone.localdate()
        asignacion.fecha_fin = None
        asignacion.activa = True
        asignacion.save(
            update_fields=[
                "sucursal",
                "fecha_inicio",
                "fecha_fin",
                "activa",
            ]
        )
    else:
        asignacion = AsignacionVehiculo.objects.create(
            sucursal=vehiculo.sucursal or conductor.sucursal,
            conductor=conductor,
            vehiculo=vehiculo,
            fecha_inicio=timezone.localdate(),
            activa=True,
        )

    return conductor, vehiculo, asignacion


@transaction.atomic
def cambiar_estado_conductor_completo(conductor_id, estado):
    """Desactiva conductor, vehículo y asignación al bloquear la cuenta."""
    if estado not in {"pendiente", "rechazado", "suspendido"}:
        raise ValidationError("El estado solicitado no es válido.")

    conductor = Conductor.objects.select_for_update().get(pk=conductor_id)
    conductor.estado_verificacion = estado
    conductor.activo = False
    conductor.save(
        update_fields=[
            "estado_verificacion",
            "activo",
        ]
    )

    AsignacionVehiculo.objects.select_for_update().filter(
        conductor=conductor,
        activa=True,
    ).update(
        activa=False,
        fecha_fin=timezone.localdate(),
    )

    vehiculos = Vehiculo.objects.select_for_update().filter(
        propietario_conductor=conductor,
        tipo_propiedad="conductor",
    )

    estado_parqueado = None
    if estado == "suspendido":
        estado_parqueado = EstadoVehiculo.objects.filter(
            codigo="parqueado",
            activo=True,
        ).first()

    for vehiculo in vehiculos:
        vehiculo.estado_verificacion = estado
        vehiculo.estado = estado_parqueado
        if estado == "rechazado" and not vehiculo.motivo_rechazo:
            vehiculo.motivo_rechazo = (
                "El registro del conductor fue rechazado."
            )
        elif estado != "rechazado":
            vehiculo.motivo_rechazo = ""
        vehiculo.save(
            update_fields=[
                "estado_verificacion",
                "estado",
                "motivo_rechazo",
            ]
        )

    return conductor
